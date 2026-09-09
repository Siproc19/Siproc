# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import UserError

try:
    from odoo.addons.base.models.res_partner import _tz_get
except ImportError:  # por si la ruta cambia en alguna versión
    def _tz_get(self):
        return [(tz, tz) for tz in sorted(pytz.all_timezones)]

_logger = logging.getLogger(__name__)

try:
    from zk import ZK
except ImportError:
    ZK = None
    _logger.warning(
        "No se encontró la librería 'pyzk'. Instálala en el servidor de Odoo "
        "con 'pip install pyzk' para poder conectar con los checadores ZKTeco."
    )


class ZkBiometricDevice(models.Model):
    _name = 'zk.biometric.device'
    _description = 'Checador biométrico ZKTeco (Steren/ZKTeco)'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True)
    ip_address = fields.Char(string='Dirección IP', required=True)
    port = fields.Integer(string='Puerto', default=4370, required=True)
    password = fields.Integer(
        string='Clave de comunicación', default=0,
        help='Clave de comunicación (comm key) configurada en el equipo. '
             'Dejar en 0 si el equipo no tiene clave configurada.')
    timeout = fields.Integer(string='Timeout (segundos)', default=10)
    force_udp = fields.Boolean(string='Forzar UDP', default=False)
    tz = fields.Selection(
        _tz_get, string='Zona horaria del equipo', default='America/Mexico_City',
        help='Zona horaria en la que está configurado el reloj interno del checador. '
             'Las marcaciones se convierten a UTC usando esta zona antes de guardarse.')
    active = fields.Boolean(default=True)
    state = fields.Selection([
        ('draft', 'Sin probar'),
        ('connected', 'Conectado'),
        ('error', 'Error de conexión'),
    ], default='draft', string='Estado', readonly=True, copy=False)
    device_name = fields.Char(string='Nombre reportado por el equipo', readonly=True, copy=False)
    firmware_version = fields.Char(string='Firmware', readonly=True, copy=False)
    last_sync = fields.Datetime(string='Última sincronización', readonly=True, copy=False)
    last_error = fields.Text(string='Último error', readonly=True, copy=False)
    log_ids = fields.One2many('zk.attendance.log', 'device_id', string='Marcaciones importadas')
    log_count = fields.Integer(compute='_compute_log_count', string='Núm. marcaciones')

    @api.depends('log_ids')
    def _compute_log_count(self):
        for device in self:
            device.log_count = len(device.log_ids)

    # ------------------------------------------------------------------
    # Conexión al equipo
    # ------------------------------------------------------------------
    def _get_connection(self):
        """Abre y devuelve una conexión pyzk al equipo. Lanza UserError con un
        mensaje entendible si algo falla."""
        self.ensure_one()
        if ZK is None:
            raise UserError(_(
                "La librería 'pyzk' no está instalada en el servidor de Odoo.\n"
                "Instálala con: pip install pyzk"))
        zk = ZK(
            self.ip_address,
            port=self.port,
            timeout=self.timeout or 10,
            password=self.password or 0,
            force_udp=self.force_udp,
            ommit_ping=False,
        )
        try:
            conn = zk.connect()
        except Exception as e:
            raise UserError(_(
                "No se pudo conectar con el checador '%(name)s' (%(ip)s:%(port)s).\n"
                "Verifica que el equipo esté encendido, en la misma red, y que la IP, "
                "puerto y clave de comunicación sean correctos.\n\nDetalle técnico: %(error)s"
            ) % {'name': self.name, 'ip': self.ip_address, 'port': self.port, 'error': e})
        return conn

    def action_test_connection(self):
        self.ensure_one()
        conn = self._get_connection()
        try:
            device_name = conn.get_device_name() or self.name
            firmware = conn.get_firmware_version() or ''
            self.write({
                'state': 'connected',
                'device_name': device_name,
                'firmware_version': firmware,
                'last_error': False,
            })
        finally:
            conn.disconnect()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Conexión exitosa'),
                'message': _('Conectado a "%(device)s" (firmware %(fw)s).') % {
                    'device': device_name, 'fw': firmware},
                'type': 'success',
                'sticky': False,
            },
        }

    # ------------------------------------------------------------------
    # Descarga y proceso de marcaciones
    # ------------------------------------------------------------------
    def _device_dt_to_utc(self, naive_dt):
        """Convierte la hora local (naive) reportada por el checador a UTC naive,
        que es como Odoo espera los campos Datetime."""
        self.ensure_one()
        tzinfo = pytz.timezone(self.tz or 'UTC')
        local_dt = tzinfo.localize(naive_dt)
        return local_dt.astimezone(pytz.utc).replace(tzinfo=None)

    def action_download_attendance(self):
        AttendanceLog = self.env['zk.attendance.log']
        Employee = self.env['hr.employee']
        total_new = 0
        total_matched = 0

        for device in self:
            conn = None
            try:
                conn = device._get_connection()
            except UserError as e:
                device.write({'state': 'error', 'last_error': str(e)})
                _logger.warning(str(e))
                continue

            try:
                try:
                    conn.disable_device()
                except Exception:
                    pass  # no todos los firmwares lo soportan; no es crítico

                records = conn.get_attendance() or []
                for rec in records:
                    device_user_id = str(rec.user_id)
                    punch_utc = device._device_dt_to_utc(rec.timestamp)

                    exists = AttendanceLog.search([
                        ('device_id', '=', device.id),
                        ('device_user_id', '=', device_user_id),
                        ('punch_datetime', '=', punch_utc),
                    ], limit=1)
                    if exists:
                        continue

                    total_new += 1
                    employee = Employee.search(
                        [('zk_device_user_id', '=', device_user_id)], limit=1)

                    log_vals = {
                        'device_id': device.id,
                        'device_user_id': device_user_id,
                        'punch_datetime': punch_utc,
                        'employee_id': employee.id if employee else False,
                    }
                    if employee:
                        total_matched += 1
                        attendance = device._process_punch(employee, punch_utc)
                        if attendance:
                            log_vals['attendance_id'] = attendance.id

                    AttendanceLog.create(log_vals)

                device.write({
                    'state': 'connected',
                    'last_sync': fields.Datetime.now(),
                    'last_error': False,
                })
            except Exception as e:
                device.write({'state': 'error', 'last_error': str(e)})
                _logger.exception('Error al sincronizar el checador %s', device.name)
            finally:
                if conn:
                    try:
                        conn.enable_device()
                    except Exception:
                        pass
                    try:
                        conn.disconnect()
                    except Exception:
                        pass

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sincronización completa'),
                'message': _('%(new)s marcaciones nuevas, %(matched)s asociadas a un empleado.') % {
                    'new': total_new, 'matched': total_matched},
                'type': 'success' if total_new else 'info',
                'sticky': False,
            },
        }

    def _process_punch(self, employee, punch_dt):
        """A partir de una marcación (fecha/hora en UTC) decide si abre un nuevo
        registro de asistencia (entrada) o cierra uno abierto (salida)."""
        self.ensure_one()
        Attendance = self.env['hr.attendance']
        open_attendance = Attendance.search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False),
        ], order='check_in desc', limit=1)

        if open_attendance:
            if punch_dt <= open_attendance.check_in:
                # marcación fuera de orden (llegó una más vieja que la entrada abierta)
                return False
            if (punch_dt - open_attendance.check_in) < timedelta(minutes=1):
                # doble marcación accidental en el mismo minuto: se ignora
                return False
            try:
                open_attendance.write({'check_out': punch_dt})
            except Exception as e:
                _logger.warning(
                    'No se pudo cerrar la asistencia de %s: %s', employee.name, e)
                return False
            return open_attendance

        try:
            return Attendance.create({'employee_id': employee.id, 'check_in': punch_dt})
        except Exception as e:
            _logger.warning(
                'No se pudo crear la asistencia de %s: %s', employee.name, e)
            return False
