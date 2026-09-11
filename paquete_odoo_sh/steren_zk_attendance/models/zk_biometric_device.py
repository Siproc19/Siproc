# -*- coding: utf-8 -*-
import logging
import secrets
from datetime import datetime, timedelta

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
        "con 'pip install pyzk' para poder conectar con los checadores ZKTeco "
        "(solo hace falta si vas a usar los botones de conexión directa; el "
        "receptor por webhook funciona sin ella)."
    )


class ZkBiometricDevice(models.Model):
    _name = 'zk.biometric.device'
    _description = 'Checador biométrico ZKTeco (Steren/ZKTeco)'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True)

    # -- Conexión directa (solo funciona si Odoo puede alcanzar la IP del
    #    equipo: Odoo autoalojado en la misma red, o con VPN. NO funciona
    #    desde Odoo.sh / Odoo Online hacia un checador en una red local). --
    ip_address = fields.Char(string='Dirección IP')
    port = fields.Integer(string='Puerto', default=4370)
    password = fields.Integer(
        string='Clave de comunicación', default=0,
        help='Clave de comunicación (comm key) configurada en el equipo. '
             'Dejar en 0 si el equipo no tiene clave configurada.')
    timeout = fields.Integer(string='Timeout (segundos)', default=10)
    force_udp = fields.Boolean(string='Forzar UDP', default=False)

    # -- Receptor por webhook (funciona siempre, incluido Odoo.sh/Online:
    #    un programa en la red del checador empuja las marcaciones aquí). --
    token = fields.Char(string='Token del enlace', readonly=True, copy=False)
    webhook_url = fields.Char(string='URL del enlace', compute='_compute_webhook_url')

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

    def _compute_webhook_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        for device in self:
            device.webhook_url = f"{base_url}/steren_zk_attendance/push"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('token'):
                vals['token'] = secrets.token_urlsafe(24)
        return super().create(vals_list)

    def action_regenerate_token(self):
        for device in self:
            device.token = secrets.token_urlsafe(24)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Token regenerado'),
                'message': _('Actualiza config.ini en la computadora de la oficina con el nuevo token.'),
                'type': 'warning',
                'sticky': True,
            },
        }

    # ------------------------------------------------------------------
    # Conexión directa (pull) — requiere que Odoo alcance la IP del equipo
    # ------------------------------------------------------------------
    def _get_connection(self):
        """Abre y devuelve una conexión pyzk al equipo. Lanza UserError con un
        mensaje entendible si algo falla."""
        self.ensure_one()
        if ZK is None:
            raise UserError(_(
                "La librería 'pyzk' no está instalada en el servidor de Odoo.\n"
                "Instálala con: pip install pyzk"))
        if not self.ip_address:
            raise UserError(_(
                "Este checador no tiene una dirección IP configurada para "
                "conexión directa. Si usas Odoo.sh/Odoo Online, usa el "
                "receptor por webhook en su lugar (ver sección 'Enlace desde "
                "la oficina' en este formulario)."))
        zk = ZK(
            self.ip_address,
            port=self.port or 4370,
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
                "Si tu Odoo corre en la nube (Odoo.sh/Odoo Online), esto es "
                "esperado: no puede alcanzar la red local de tu oficina. Usa "
                "el receptor por webhook en su lugar.\n\n"
                "Si tu Odoo sí está en la misma red que el checador, verifica "
                "que el equipo esté encendido y que la IP, puerto y clave de "
                "comunicación sean correctos.\n\nDetalle técnico: %(error)s"
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

    def action_download_attendance(self):
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
                punches = [
                    {'device_user_id': str(rec.user_id), 'timestamp': rec.timestamp}
                    for rec in records
                ]
                stats = device._process_incoming_punches(punches)
                total_new += stats['new']
                total_matched += stats['matched']

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

    # ------------------------------------------------------------------
    # Procesamiento de marcaciones — usado tanto por la conexión directa
    # (pull, arriba) como por el receptor de webhook (push, en
    # controllers/main.py), para no duplicar la lógica.
    # ------------------------------------------------------------------
    def _device_dt_to_utc(self, naive_dt):
        """Convierte la hora local (naive) reportada por el checador a UTC naive,
        que es como Odoo espera los campos Datetime."""
        self.ensure_one()
        tzinfo = pytz.timezone(self.tz or 'UTC')
        local_dt = tzinfo.localize(naive_dt)
        return local_dt.astimezone(pytz.utc).replace(tzinfo=None)

    def _process_incoming_punches(self, punch_dicts):
        """punch_dicts: iterable de dicts {'device_user_id': str, 'timestamp': datetime
        naive en hora LOCAL del equipo, o str 'YYYY-MM-DD HH:MM:SS'}.

        Aplica deduplicación, vincula con el empleado, abre/cierra asistencias,
        y devuelve un resumen: {'received', 'new', 'matched', 'errors'}."""
        self.ensure_one()
        AttendanceLog = self.env['zk.attendance.log']
        Employee = self.env['hr.employee']
        stats = {'received': 0, 'new': 0, 'matched': 0, 'errors': 0}

        for item in punch_dicts:
            stats['received'] += 1
            try:
                device_user_id = str(item.get('device_user_id') or '').strip()
                raw_ts = item.get('timestamp')
                if not device_user_id or not raw_ts:
                    stats['errors'] += 1
                    continue
                if isinstance(raw_ts, str):
                    local_dt = datetime.strptime(raw_ts[:19], '%Y-%m-%d %H:%M:%S')
                elif isinstance(raw_ts, datetime):
                    local_dt = raw_ts
                else:
                    stats['errors'] += 1
                    continue
                punch_utc = self._device_dt_to_utc(local_dt)
            except Exception:
                _logger.warning(
                    'Marcación con formato inválido de %s, se ignora: %r',
                    self.name, item)
                stats['errors'] += 1
                continue

            exists = AttendanceLog.search([
                ('device_id', '=', self.id),
                ('device_user_id', '=', device_user_id),
                ('punch_datetime', '=', punch_utc),
            ], limit=1)
            if exists:
                continue

            stats['new'] += 1
            employee = Employee.search(
                [('zk_device_user_id', '=', device_user_id)], limit=1)

            log_vals = {
                'device_id': self.id,
                'device_user_id': device_user_id,
                'punch_datetime': punch_utc,
                'employee_id': employee.id if employee else False,
            }
            if employee:
                stats['matched'] += 1
                attendance = self._process_punch(employee, punch_utc)
                if attendance:
                    log_vals['attendance_id'] = attendance.id

            AttendanceLog.create(log_vals)

        return stats

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
