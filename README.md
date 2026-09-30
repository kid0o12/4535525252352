# 🎛️ TempRole Manager

Bot de Discord para gestionar **roles temporales**.

## ✨ Funciones

- `/addrole @usuario @rol 7d`
- `/remove_role @usuario @rol`
- `/roltime @usuario`
- `/temproles`
- `/rolinfo @rol`
- `/settings #canal`
- `/temprolehelp`
- Persistencia en `data/roles.json`
- Eliminación automática al expirar
- Avisos de expiración
- Renovación/acumulación del tiempo
- Embeds diseñados
- Botones de ayuda
- Comprobación de jerarquía de roles
- Sistema de logs por servidor

## 🛠️ Instalación

### 1. Instala Python

Se recomienda Python 3.11 o superior.

### 2. Instala dependencias

```bash
pip install -r requirements.txt
```

### 3. Configura el bot

Abre `config.json`:

```json
{
    "token": "TU_TOKEN",
    "guild_id": 123456789012345678,
    "log_channel_id": 0,
    "prefix": "!"
}
```

`guild_id` puede ser el ID de tu servidor. Si lo pones, los slash commands se sincronizan rápidamente en ese servidor.

`log_channel_id` es opcional. También puedes configurarlo desde Discord con:

```text
/settings #canal
```

### 4. Permisos del bot

Al invitarlo, dale como mínimo:

- View Channels
- Send Messages
- Embed Links
- Manage Roles
- Read Message History

Y MUY IMPORTANTE:

**El rol del bot debe estar por encima de todos los roles que quieras gestionar.**

### 5. Ejecutar

```bash
python bot.py
```

## ⏱️ Formatos de duración

```text
30s
30m
2h
7d
2w
```

También funcionan:

```text
30 minutes
2 hours
7 days
2 weeks
```

## 🔄 Renovación

Si un usuario ya tiene un rol temporal:

```text
/addrole @Usuario @VIP 7d
```

y todavía le quedan 3 días, añadir otros 7 días hará que tenga:

```text
10 días restantes
```

## 💾 Persistencia

Los temporizadores se guardan en:

```text
data/roles.json
```

Si reinicias el bot, los temporizadores siguen existiendo.

## 🔐 Seguridad

`/addrole` y `/remove_role` requieren **Gestionar roles**.

`/settings` requiere **Gestionar servidor**.

El bot no puede gestionar:

- `@everyone`
- Roles gestionados por integraciones
- Roles que estén por encima o al mismo nivel que el bot

## 📌 Importante

No compartas nunca el token de tu bot. Si lo publicas accidentalmente, regénéralo desde el Discord Developer Portal.
