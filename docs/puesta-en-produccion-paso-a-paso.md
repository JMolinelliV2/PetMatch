# MascoMatch: procedimiento de puesta en producción

Fecha: 22 de octubre de 2026. Preparado a partir del código y los scripts del repositorio; no se ejecutó un despliegue en un VPS real durante la preparación de esta guía.

## Alcance y resultado esperado

Esta guía instala MascoMatch completo en **un VPS Linux nuevo**, con una base nueva. Incluye web, API, PostgreSQL, Redis, SeaweedFS, IA local al servidor, correo, HTTPS y respaldos B2. La computadora personal se usa para administrar el servidor por SSH; puede apagarse después sin interrumpir el sitio.

No hace falta contratar PostgreSQL, Redis o almacenamiento operativo de fotos por separado: este despliegue los ejecuta en el VPS. B2 guarda copias externas de recuperación. El dominio permanece en Hostinger.

**Si se quieren conservar las cuentas, avisos o fotos de la instalación local, detenerse antes del primer despliegue y preparar una migración con respaldo/restauración.** Publicar el código no transfiere esos datos. No copiar `.env`, contraseñas de prueba ni volúmenes de Docker Desktop como si fueran la configuración de producción.

Se distinguen tres lugares:

- **PC / PowerShell:** conectarse al servidor y administrar claves SSH.
- **VPS / terminal Linux:** instalar y ejecutar la aplicación.
- **Panel web:** Hostinger, Brevo, proveedor del VPS y Backblaze.

Los comandos Linux no se pegan en PowerShell sin haber entrado antes por SSH. Reemplazar `IP_VPS`, `USUARIO_INICIAL`, `LOGIN_SMTP`, `REGION` y `BUCKET` por sus valores reales. No escribir los símbolos `< >` alrededor de esos valores.

## Orden de trabajo

1. Contratar y preparar el VPS.
2. Configurar acceso SSH y firewall.
3. Obtener el repositorio e instalar Docker.
4. Generar configuración privada.
5. Configurar Brevo y direcciones.
6. Apuntar DNS al servidor.
7. Desplegar la aplicación y sus modelos.
8. Comprobar HTTPS, correo y flujos públicos.
9. Asignar la cuenta administradora.
10. Activar B2 y probar recuperación.
11. Completar monitoreo, mantenimiento y revisión de lanzamiento.

---

## 1. Crear el VPS

**Dónde: panel del proveedor del VPS.**

Seleccionar:

| Campo | Valor para esta guía |
| --- | --- |
| Sistema | Ubuntu **24.04 LTS** limpio |
| Arquitectura | **x86-64 / amd64** |
| CPU | Punto de partida: 8 vCPU; evaluar capacidad sostenida del plan |
| RAM | Punto de partida: 24 GB o más; 32 GB deja más margen |
| Disco | SSD de al menos 100 GB, con margen para imágenes, modelos, fotos y respaldos |
| Dirección | IPv4 pública estable |
| Acceso | SSH y consola de recuperación desde el panel |

Los recursos se basan en los límites y el objetivo de despliegue del proyecto. No son una garantía de rendimiento ni de cantidad de usuarios: se medirán en ese servidor. Evitar una imagen de WordPress o un constructor de sitios. El bootstrap actual requiere Ubuntu 24.04 y amd64; no elegir otra versión o ARM sin adaptar y comprobar la instalación.

Guardar la IP, usuario inicial, acceso al panel y mecanismo de recuperación. Si el proveedor ofrece snapshots, pueden complementar B2, pero no sustituyen la restauración verificada de la aplicación.

**Resultado esperado:** servidor creado y acceso a su consola disponible.

## 2. Preparar una clave SSH en Windows

**Dónde: PC / PowerShell.**

Comprobar si ya existe una clave específica para este servidor:

```powershell
Test-Path "$env:USERPROFILE\.ssh\mascomatch_vps"
```

Si devuelve `False`, generarla:

```powershell
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\mascomatch_vps" -C "MascoMatch VPS"
```

Elegir una frase de protección. Si el archivo ya existe, conservarlo; no sobrescribir una clave en uso. Mostrar únicamente la parte pública:

```powershell
Get-Content "$env:USERPROFILE\.ssh\mascomatch_vps.pub"
```

Agregar esa clave pública al VPS desde el panel cuando el proveedor lo permita. El archivo sin `.pub` es privado y permanece en la computadora o gestor seguro del operador.

Conectarse con el usuario inicial que indique el proveedor:

```powershell
ssh -i "$env:USERPROFILE\.ssh\mascomatch_vps" USUARIO_INICIAL@IP_VPS
```

Si la instalación inicial utiliza contraseña, entrar por el método que entregue el proveedor y configurar la clave en el paso siguiente. En la primera conexión, comprobar la huella del servidor con la consola o información del proveedor antes de aceptarla.

**Resultado esperado:** una terminal Linux del VPS, ya no el prompt habitual de PowerShell.

## 3. Crear el usuario administrador del despliegue

**Dónde: VPS / sesión inicial con permisos administrativos.**

Para no depender del usuario root en la administración habitual:

```sh
sudo adduser mascomatch
sudo usermod -aG sudo mascomatch
sudo install -d -m 700 -o mascomatch -g mascomatch /home/mascomatch/.ssh
sudo nano /home/mascomatch/.ssh/authorized_keys
```

Pegar la clave **pública** del paso 2, completa y en una línea. Guardar con `Ctrl+O`, Enter, y salir con `Ctrl+X`. Aplicar permisos:

```sh
sudo chown mascomatch:mascomatch /home/mascomatch/.ssh/authorized_keys
sudo chmod 600 /home/mascomatch/.ssh/authorized_keys
```

Mantener abierta esta primera sesión. Abrir otra ventana de PowerShell y comprobar el acceso del usuario nuevo:

```powershell
ssh -i "$env:USERPROFILE\.ssh\mascomatch_vps" mascomatch@IP_VPS
```

En la nueva sesión:

```sh
sudo -v
```

Continuar desde ese usuario. Si ya existe una cuenta administrativa equivalente, se pueden adaptar los nombres; no crear usuarios duplicados. Mantener disponible la consola del proveedor.

**Resultado esperado:** SSH con clave y `sudo` funcionando para el operador.

## 4. Actualizar Ubuntu, comprobar reloj y configurar firewall

**Dónde: VPS / usuario `mascomatch`.**

```sh
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get install -y git python3 nano ca-certificates curl
sudo timedatectl set-ntp true
timedatectl status
dpkg --print-architecture
free -h
df -h /
```

Comprobar arquitectura `amd64`, espacio disponible y sincronización del reloj. Si Ubuntu solicita reiniciar, hacerlo antes de continuar y volver a entrar por SSH.

**En el firewall del proveedor**, permitir:

| Puerto | Origen | Uso |
| --- | --- | --- |
| TCP 22, o el SSH elegido | IP del operador, cuando sea posible | Administración |
| TCP 80 | Público | HTTP y validación HTTPS |
| TCP 443 | Público | Sitio HTTPS |
| UDP 443 | Público, opcional | HTTP/3 |

Mantener permitido el tráfico saliente necesario para paquetes, imágenes/modelos, DNS, sincronización horaria, SMTP 587 y HTTPS hacia B2. No publicar puertos de DB, Redis, fotos, Ollama ni Prometheus.

Usar el firewall del proveedor como control exterior. Docker advierte que los puertos publicados pueden pasar por fuera de reglas UFW; no asumir protección solo por activar UFW. El Compose de producción mantiene privados los servicios de datos. [Docker: firewall e instalación Ubuntu](https://docs.docker.com/engine/install/ubuntu/).

**Resultado esperado:** acceso administrativo conservado y únicamente los puertos públicos necesarios admitidos.

## 5. Obtener el repositorio

**Dónde: VPS.**

Si el repositorio permite lectura pública:

```sh
cd ~
git clone https://github.com/JMolinelliV2/MascoMatch.git
cd ~/MascoMatch
git log -1 --oneline
git status --short
```

La revisión `86f0db3` contiene la integración B2; utilizar esa revisión aprobada o una posterior que también haya sido revisada. No desplegar una copia antigua que no tenga `compose.production.yml` y los scripts actuales.

### Si GitHub indica que el repositorio es privado

Crear en el VPS una clave de despliegue separada de la clave de acceso al servidor:

```sh
ssh-keygen -t ed25519 -f ~/.ssh/mascomatch_github -C "MascoMatch VPS repository read-only"
cat ~/.ssh/mascomatch_github.pub
```

En GitHub: repositorio → **Settings → Deploy keys → Add deploy key**. Pegar la clave pública y dejar **sin habilitar** el acceso de escritura. Guardar la clave privada en el VPS.

Editar `~/.ssh/config` y agregar, conservando cualquier configuración existente:

```text
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/mascomatch_github
    IdentitiesOnly yes
```

```sh
chmod 600 ~/.ssh/config
cd ~
git clone git@github.com:JMolinelliV2/MascoMatch.git
cd ~/MascoMatch
git log -1 --oneline
```

Usar esta alternativa si el clon HTTPS todavía no se completó; no clonar encima de una carpeta existente. No poner tokens personales ni contraseñas en la URL del repositorio.

**Resultado esperado:** repositorio en `/home/mascomatch/MascoMatch`.

## 6. Instalar Docker Engine y Compose

**Dónde: VPS, dentro de `~/MascoMatch`.**

```sh
sudo sh tools/bootstrap_server.sh
sudo usermod -aG docker mascomatch
```

El script instala Docker Engine, Buildx y el plugin Compose desde el repositorio oficial de Docker. No se necesita Docker Desktop en el VPS.

Cerrar la sesión SSH del usuario y volver a conectarse para aplicar el grupo:

```sh
exit
```

**PC / PowerShell:**

```powershell
ssh -i "$env:USERPROFILE\.ssh\mascomatch_vps" mascomatch@IP_VPS
```

**VPS:**

```sh
cd ~/MascoMatch
docker version
docker compose version
```

La cuenta del grupo Docker tiene capacidad administrativa sobre contenedores y el host; reservarla al operador. Si aparece `permission denied`, revisar el grupo y la nueva sesión en vez de cambiar permisos del socket de Docker.

**Resultado esperado:** comandos Docker sin errores de permisos ni de conexión al daemon.

## 7. Generar la configuración privada una sola vez

**Dónde: VPS, dentro de `~/MascoMatch`.**

```sh
python3 tools/production_init.py --domain mascomatch.com
```

Esto crea:

- `.env.production`: dominio, opciones de correo, IA, país, backups y otros valores de despliegue.
- `.secrets/`: claves aleatorias distintas para base, Redis, sesiones, fotos, métricas y cifrado de backups; archivos B2/SMTP inicialmente vacíos.

El generador se niega a sobrescribir una instalación existente. Si informa que los archivos ya existen, conservarlos y editar esa instalación; no borrar claves para conseguir que vuelva a ejecutar.

No copiar el `.env` de desarrollo. No publicar ni subir `.secrets` a GitHub. Evitar imprimir `.env.production`, secretos o la salida completa de `docker compose config` en registros compartidos.

### Copia de la clave de recuperación

Guardar `.secrets/backup_key` en un gestor privado o una ubicación segura **independiente del VPS**. Se puede transferir por SFTP/SSH a una ubicación privada del operador y luego guardarla cifrada. Por ejemplo, desde PowerShell, a una carpeta privada que ya exista:

```powershell
scp -i "$env:USERPROFILE\.ssh\mascomatch_vps" mascomatch@IP_VPS:/home/mascomatch/MascoMatch/.secrets/backup_key RUTA_PRIVADA_EXISTENTE
```

No usar la carpeta del repositorio como destino ni una carpeta pública/sin protección. Esta copia es administrativa; el sitio no necesita que la PC esté encendida. Sin la clave original no se pueden descifrar los respaldos B2.

**Resultado esperado:** configuración generada y clave AES guardada fuera del servidor.

## 8. Configurar dominio y correo en `.env.production`

**Dónde: VPS.**

```sh
nano .env.production
```

Editar estas líneas, conservando el resto de los valores generados:

```dotenv
SITE_DOMAIN=mascomatch.com
WEB_ORIGIN=https://mascomatch.com
PUBLIC_SITE_URL=https://mascomatch.com
ALLOWED_HOSTS=mascomatch.com,localhost,127.0.0.1,api

MAIL_DELIVERY_MODE=smtp
SMTP_HOST=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USERNAME=LOGIN_SMTP
SMTP_FROM=MascoMatch <info@mascomatch.com>
SMTP_TLS_MODE=starttls

NEXT_PUBLIC_SEARCH_COUNTRY=UY
BACKUP_INTERVAL_SECONDS=21600
BACKUP_LOCAL_KEEP=14
OFFSITE_BACKUP_ENABLED=false
```

`LOGIN_SMTP` es el login actual del panel de Brevo, no necesariamente el correo personal de la cuenta. La contraseña del envío debe ser la **SMTP key**, no la API key. [Configuración SMTP oficial](https://help.brevo.com/hc/en-us/articles/7924908994450-Send-transactional-emails-using-Brevo-SMTP).

Guardar la clave SMTP sin ponerla en un comando:

```sh
chmod 600 .secrets/smtp_password
nano .secrets/smtp_password
chmod 444 .secrets/smtp_password
```

En el editor, pegar solo el valor de la clave, sin comillas ni `SMTP_PASSWORD=`. Los archivos individuales vuelven a `0444` para los montajes de Docker; el directorio `.secrets` permanece privado en `0700`.

**En Brevo:** comprobar que `mascomatch.com` sigue autenticado y que `info@mascomatch.com` es un remitente habilitado. Se mantienen los registros DNS de correo que ya funcionan. Revisar cuota y estado del servicio para que confirmaciones y alertas no queden demoradas.

Si todavía no está resuelta la configuración de medición/cookies del lanzamiento, usar `ANALYTICS_ENABLED=false` mientras se revisa. Esto detiene nuevos eventos de medición de producto; las funciones operativas y el seguimiento de respuestas de coincidencias son independientes. Si se mantiene activo, revisar la política publicada y el criterio de consentimiento aplicable antes de captar visitantes.

**Resultado esperado:** configuración del dominio público y envío SMTP real preparada; B2 sigue apagado hasta su comprobación específica.

## 9. Definir la búsqueda de direcciones y los mapas

La web ya busca mediante una API compatible con **Photon**. No hace falta una API key de Google Maps para la configuración actual.

Para un piloto de poco tráfico, se puede añadir a `.env.production`:

```dotenv
GEOCODER_BASE_URL=https://photon.komoot.io
```

Es el servidor público de demostración: permite uso razonable, puede limitar/bloquear uso intensivo y no garantiza disponibilidad. Para tráfico sostenido, contratar o desplegar un endpoint compatible y reemplazar esa URL antes de ampliar el lanzamiento. No apuntarla directamente a Google o Geoapify: no implementan el mismo contrato del endpoint actual. [Condiciones publicadas por Photon](https://github.com/komoot/photon#demo-server).

`NEXT_PUBLIC_SEARCH_COUNTRY=UY` se incorpora al construir la web. Si se cambia el país, reconstruir/desplegar la web; un simple reinicio no sustituye el build.

Leaflet muestra el mapa con tiles de OpenStreetMap en el código actual. Conservar la atribución visible, las cachés del navegador y la política de uso; no agregar descargas masivas ni asumir un servicio ilimitado. Cambiar de proveedor de tiles también puede requerir ajustar la política de imágenes de Caddy. [Política oficial de tiles](https://operations.osmfoundation.org/policies/tiles/).

**Resultado esperado:** decisión explícita para el piloto y endpoint compatible definido. Si se espera mucho tráfico desde el comienzo, resolver este proveedor antes de abrir la convocatoria.

## 10. Configurar DNS en Hostinger

**Dónde: Hostinger → Dominios → mascomatch.com → Administrar → DNS / Nameservers.**

Editar únicamente los registros web correspondientes a MascoMatch:

| Tipo | Nombre | Contenido | TTL orientativo |
| --- | --- | --- | --- |
| A | `@` | `IP_VPS` | 300 s o valor permitido por el panel |
| CNAME | `www` | `mascomatch.com` | 300 s o valor permitido |

Evitar varios A con destinos distintos para `@`. Si hay AAAA antiguo y no se configuró IPv6 en este VPS, retirarlo para no enviar visitantes al servidor anterior. Conservar MX, SPF, DKIM, DMARC y las verificaciones de Brevo/Hostinger; no cambiar nameservers para hacer este despliegue. No modificar el DNS de otro dominio alojado en la misma cuenta.

El A de raíz es el que permite atender `https://mascomatch.com`. El CNAME de `www` prepara su resolución, pero **el soporte HTTPS/redirección de www necesita el paso opcional 12**. [Guía de Hostinger sobre apuntar un dominio al VPS](https://www.hostinger.com/support/1583227-how-to-point-a-domain-to-your-vps-at-hostinger/).

**PC / PowerShell:**

```powershell
Resolve-DnsName mascomatch.com -Type A
```

Comprobar que aparece la IP del VPS elegido, no la del hosting web anterior. Los cambios dependen de cachés y propagación; esperar a que la resolución correcta sea visible antes de diagnosticar HTTPS.

**Resultado esperado:** el dominio raíz apunta al VPS y se conserva el correo existente.

## 11. Primer despliegue con IA en el VPS

**Dónde: VPS, dentro de `~/MascoMatch`.**

Para que el trabajo largo continúe aunque se corte SSH, crear primero una sesión persistente:

```sh
sudo apt-get install -y tmux
tmux new -s mascomatch-despliegue
```

Si esa sesión ya existe, recuperarla con `tmux attach -t mascomatch-despliegue` en lugar de crear otra. Dentro de ella, volver a `cd ~/MascoMatch` si hace falta. Para dejarla trabajando y desconectarse, pulsar `Ctrl+B`, soltar y pulsar `D`; para regresar, reconectar por SSH y usar `tmux attach`.

Crear una función para los comandos de operación de esta guía:

```sh
dc() {
  docker compose -p mascomatch --env-file .env.production -f compose.production.yml --profile ai-local --profile monitoring "$@"
}
```

La función vive solo en esa sesión; volver a definirla al reconectarse si se necesita. Validar sin mostrar secretos:

```sh
dc config --quiet
```

Leer los [términos de Gemma](https://ai.google.dev/gemma/terms) y la [política de usos prohibidos](https://ai.google.dev/gemma/prohibited_use_policy). **Solo si el propietario los acepta**, ejecutar:

```sh
python3 tools/production_apply.py deploy --with-ai --accept-gemma-terms
```

El script construye imágenes, prepara DB/fotos, migra el esquema, hace un respaldo local, instala/verifica los modelos fijados, prepara trabajos y arranca API, web, Caddy, workers, Ollama, backups y Prometheus. No cambiar nombres ni versiones de modelos durante esta primera puesta en marcha.

La primera instalación descarga varios GB y realiza trabajo de CPU. No se promete un tiempo fijo. Si el proceso falla, leer el paso y corregirlo; el script puede repetirse conservando los volúmenes. En una instalación incompleta de Gemma, repetir la opción de aceptación solo después de haberla aceptado; sin ella el script verifica una instalación existente.

```sh
dc ps
python3 tools/production_apply.py check
```

Servicios continuos deben estar `running`/`healthy` cuando tengan healthcheck. `migrate` y `photos-init` son tareas de una sola ejecución: salida `0` es esperable. Caddy y fotos no exponen un healthcheck equivalente al de API; verificar sus registros si hay problemas.

**Resultado esperado:** el chequeo devuelve `ready: true`; DB, colas, fotos, workers/modelos, respaldo reciente y SMTP configurado pasan sus verificaciones. Ese chequeo no certifica entrega de correo, precisión del reconocimiento ni recuperación real B2.

## 12. Comprobar HTTPS y, opcionalmente, agregar www

**PC / navegador:** abrir `https://mascomatch.com`.

**VPS:**

```sh
curl -I https://mascomatch.com
curl -fsS https://mascomatch.com/api/health
curl -fsS 'https://mascomatch.com/api/v1/public/lost-animals?limit=1'
```

La primera debe devolver una respuesta HTTPS normal, la segunda confirma el proceso web y la tercera una lectura pública de API/base. No son un chequeo completo de Redis, fotos o IA. Para dependencias usar `production_apply.py check` y `/admin`. `/health/ready` es privado desde el exterior por diseño.

Caddy obtiene y renueva certificados cuando DNS apunta al VPS, 80/443 son accesibles y sus volúmenes persisten. [Requisitos de HTTPS automático](https://caddyserver.com/docs/automatic-https). Si falla:

```sh
dc logs --tail 100 caddy
```

### www, si se quiere ofrecer también

La configuración versionada actual atiende el dominio raíz. Para `www`, conservar el CNAME del paso 10 y agregar al final de `infrastructure/production/Caddyfile`, **fuera** del bloque existente:

```caddyfile
www.mascomatch.com {
    redir https://mascomatch.com{uri} permanent
}
```

Validar y cargar la configuración sin reiniciar la aplicación:

```sh
dc exec -T caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
dc exec -T caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
```

Comprobar `https://www.mascomatch.com` y su redirección al dominio raíz. Esta edición debe incorporarse al repositorio aprobado para que quede documentada en actualizaciones; no hacer `git reset` ni descartar la modificación del servidor. Si no se agrega, anunciar únicamente el dominio raíz.

**Resultado esperado:** HTTPS sin advertencias de certificado; si se habilitó www, redirección al dominio raíz conservando la ruta.

## 13. Reservar la cuenta administradora

**Dónde: VPS.**

```sh
dc exec -T api python -m app.admin --email info@mascomatch.com
```

El comando reserva esa dirección, o habilita el acceso si ya existe y está confirmada. La asignación de la instalación local no se transfiere automáticamente a esta nueva base.

**Dónde: navegador público.**

1. Crear la cuenta `info@mascomatch.com` en el registro de MascoMatch.
2. Elegir una contraseña nueva, distinta de SMTP y de las claves del servidor.
3. Abrir el correo de confirmación y completar la confirmación.
4. Volver a ingresar y abrir `/admin`.
5. Comprobar que otra cuenta normal no puede entrar a ese panel.

**Resultado esperado:** administración habilitada exclusivamente para la cuenta asignada y confirmada.

## 14. Comprobar correo y los flujos del sitio

**VPS — correo solicitado explícitamente para el operador:**

```sh
dc exec -T api python -m app.ops.release_check --send-test-email info@mascomatch.com
```

Abrir el mensaje en la casilla real y revisar spam. `SMTP aceptado` no equivale a `correo recibido`.

**Navegador público — con cuentas/casos de prueba identificables:**

| Recorrido | Comprobar |
| --- | --- |
| Registro | Llega confirmación, enlace funciona y habilita la cuenta |
| Ingreso/salida | Acceso correcto y sesión cerrada al salir |
| Recuperar contraseña | Correo con enlace de producción, cambio de contraseña y nuevo ingreso |
| Perdí una mascota | Pasos, campos, fotos, ubicación, pin ajustable y publicación |
| Sin foto | Aviso inmediato y posterior recordatorio conforme a la configuración |
| Mascotas perdidas | Miniatura, ficha, ID único y fotos ampliables |
| Mapa | Pines, miniaturas, ubicación y regreso al mapa desde el aviso |
| Avistamiento desde una ficha | Flujo breve, pista vinculada y notificación al dueño |
| Avistamiento general / encontrado | Explicación correcta del formulario y reporte visible |
| Coincidencias | Trabajos terminan; dueño puede responder sin confundir identificación con recuperación |
| Mascota recuperada | El aviso cambia de estado y se puede solicitar una reseña |
| Mi cuenta | Contactos, preferencias y confirmación de guardado |
| Notificaciones | Lectura/archivo y acceso condicionado a sesión |
| Contacto | El mensaje llega a `info@mascomatch.com` |
| Administración | Trabajos, intentos de correo, contactos, avisos y respaldos consultables |

Usar ubicaciones y fotos de prueba autorizadas y retirar/cerrar los avisos de prueba al terminar. No enviar pruebas masivas a terceros. En los correos, verificar que los enlaces comiencen con `https://mascomatch.com`, nunca `localhost`.

**VPS — prueba técnica de inferencia, después del despliegue y sin carga importante:**

```sh
python3 tools/production_apply.py smoke
```

Ese smoke descarga fixtures de prueba y crea/elimina su DB y registros desechables. Usa recursos/modelos del servidor y el almacenamiento/Redis compartidos bajo referencias propias; no es una prueba de volumen ni una medición de precisión sobre animales reales. Si hay usuarios, elegir una ventana tranquila.

**Resultado esperado:** flujos públicos correctos, correo real recibido y trabajos de IA técnicamente procesados. La calidad de coincidencias se seguirá midiendo con las respuestas de los dueños.

## 15. Crear y proteger el bucket B2 de producción

**Dónde: Backblaze B2 Cloud Storage.**

1. Crear la cuenta y proteger el acceso del propietario.
2. Crear un bucket privado exclusivo, por ejemplo un nombre disponible basado en `mascomatch-production-backups`.
3. Elegir región y guardar nombre, región y endpoint S3 exactos.
4. Habilitar **Object Lock** y default **COMPLIANCE, 30 días**.
5. Configurar lifecycle sobre `backups/`:

```json
[
  {
    "fileNamePrefix": "backups/",
    "daysFromUploadingToHiding": 31,
    "daysFromHidingToDeleting": 1,
    "daysFromStartingToCancelingUnfinishedLargeFiles": 1
  }
]
```

Object Lock, una vez habilitado, no puede desactivarse en ese bucket; COMPLIANCE no permite quitar la protección vigente para borrar anticipadamente. El archivo permanece protegido por 30 días más el margen de transferencia aplicado por el código. Lifecycle oculta y elimina posteriormente, según su procesamiento; no significa eliminación exacta al cumplir 30 días. [Object Lock](https://www.backblaze.com/docs/cloud-storage-object-lock), [lifecycle](https://www.backblaze.com/docs/en/cloud-storage-lifecycle-rules).

Crear una **Application Key dedicada**, restringida al bucket y preferentemente a `backups/`, con:

```text
listBuckets,readBuckets,listFiles,readFiles,writeFiles,readBucketRetentions,readFileRetentions,writeFileRetentions
```

Si el panel no permite seleccionar ese conjunto exacto, seguir el alta con CLI de la [guía B2 del repositorio](backblaze-backup.md#3-application-key-dedicada). No usar master key ni otorgar borrado/administración de buckets. `listAllBucketNames` no se solicita por defecto porque este código no enumera todos los buckets; comprobar los permisos mínimos con el comando de conexión real. [Capacidades S3 de B2](https://www.backblaze.com/docs/cloud-storage-s3-compatible-app-keys).

Guardar el key ID y la application key en un gestor privado: la clave se muestra al crearla y no se recupera después desde el listado.

**Resultado esperado:** bucket privado con bloqueo/lifecycle y una clave exclusiva de alcance limitado.

## 16. Configurar y activar B2 en el VPS

**Dónde: VPS.**

Los archivos vacíos ya los creó `production_init`. Si se actualiza una instalación anterior, añadir solo los faltantes con `python3 tools/production_init.py --prepare-b2-secrets`.

```sh
chmod 600 .secrets/b2_key_id .secrets/b2_application_key
nano .secrets/b2_key_id
nano .secrets/b2_application_key
chmod 444 .secrets/b2_key_id .secrets/b2_application_key
```

Pegar solo cada valor en su archivo. Editar `.env.production`, conservando todavía la bandera en `false`:

```dotenv
OFFSITE_BACKUP_ENABLED=false
B2_ENDPOINT=https://s3.REGION.backblazeb2.com
B2_REGION=REGION
B2_BUCKET=BUCKET
B2_OBJECT_LOCK_ENABLED=true
B2_OBJECT_LOCK_DAYS=30
B2_OPERATION_TIMEOUT_SECONDS=900
OFFSITE_RETRY_INTERVAL_SECONDS=900
OFFSITE_DEEP_VERIFY_INTERVAL_SECONDS=604800
```

Reemplazar región y bucket por sus valores reales; no usar el endpoint de las fotos operativas. Comprobar acceso sin subir datos:

```sh
dc run --rm --no-deps -e OFFSITE_BACKUP_ENABLED=true backup python -m app.ops.backup check-offsite
```

Si confirma bucket privado/retención, detener el daemon para que no compita con los comandos manuales:

```sh
dc stop backup
nano .env.production
```

Cambiar `OFFSITE_BACKUP_ENABLED=true`. Crear una copia local y remota, listar y autenticar la descarga:

```sh
dc run --rm --no-deps backup python -m app.ops.backup create /backups
dc run --rm --no-deps backup python -m app.ops.backup list-offsite --retention --limit 20
dc run --rm --no-deps backup python -m app.ops.backup verify-offsite --deep
```

Abrir Backblaze y confirmar que aparecen los `.mbak`, sus tamaños y retención. Guardar el `key` y `version_id` de una copia verificada en el registro privado de operación. El SHA no depende de ETag.

Reiniciar el servicio con la configuración nueva:

```sh
dc up -d --no-deps --force-recreate backup
dc logs --tail 60 backup
```

En `/admin`, comprobar última copia local, última copia remota, fecha de captura recuperable y pendientes. Un comando ocupado devuelve 2: esperar o detener el daemon, nunca eliminar el archivo de bloqueo para forzar concurrencia.

**Resultado esperado:** copia remota verificada, Object Lock observado, pendientes procesados y daemon activo para las próximas capturas de seis horas.

## 17. Hacer un simulacro de recuperación B2

No basta con ver un objeto en Backblaze. Crear **otro bucket de prueba** cuyo nombre empiece por `mascomatch-drill-`, con igual privacidad, Object Lock, lifecycle y una clave exclusiva de ese bucket.

El simulacro puede ejecutarse en la PC con Docker Desktop disponible o en otro entorno de pruebas con recursos suficientes. No correrlo en paralelo al primer despliegue/inferencia en un VPS ajustado de memoria. Su stack es separado y no publica puertos, pero consume CPU, RAM y disco.

**En el entorno de pruebas, dentro del repositorio:**

```sh
python3 tools/production_validate.py --keep
```

En Windows usar `python` si es el nombre de su Python instalado. Esto genera el entorno y archivos privados de `real-data/production-preview` con correo capturado en Mailpit; no manda correos reales.

1. Colocar los dos secretos del **bucket de prueba** en `real-data/production-preview/.secrets/b2_key_id` y `b2_application_key` mediante un editor privado.
2. Crear `real-data/b2-drill.env` con solo endpoint, región, bucket `mascomatch-drill-*`, `B2_OBJECT_LOCK_ENABLED=true` y `B2_OBJECT_LOCK_DAYS=30`.
3. Ejecutar:

```sh
python3 tools/production_validate.py --with-b2 --b2-env-file real-data/b2-drill.env
```

La prueba sube un respaldo sintético cifrado, comprueba bloqueo, descarga, autentica, restaura en DB/fotos vacías y compara registros y hashes. Imprime el objeto/versión retenidos. El archivo de prueba queda protegido en B2 hasta su vencimiento/lifecycle; no se borra anticipadamente ni se deja sin referencia. El stack temporal se elimina al terminar salvo que se use `--keep`.

Guardar resultado y duración. Esto prueba la integración y el recorrido de restore con datos sintéticos. La recuperación de un backup de producción en un servidor nuevo tiene su procedimiento específico y destinos vacíos en [la guía B2](backblaze-backup.md#9-recuperación-manual-desde-b2-ante-pérdida-del-servidor).

**Resultado esperado:** simulacro terminado correctamente, clave AES recuperable fuera del VPS y tiempos anotados. No declarar operativo el disaster recovery antes de completar esta comprobación.

## 18. Completar monitoreo y envío de alertas

### Lo que está disponible

- Resumen administrativo de usuarios, trabajos, correo, contactos y backups.
- Prometheus privado en el VPS, puerto `127.0.0.1:9090`.
- Reglas para disponibilidad, demoras, fallos de correo, backups vencidos, poco espacio y verificación profunda pendiente.

**PC / PowerShell, para inspeccionar Prometheus sin publicarlo:**

```powershell
ssh -i "$env:USERPROFILE\.ssh\mascomatch_vps" -L 9090:127.0.0.1:9090 mascomatch@IP_VPS
```

Abrir `http://localhost:9090` mientras el túnel esté abierto. Revisar Targets y Alerts. Cerrar el túnel no detiene Prometheus ni el sitio.

### Trabajo todavía necesario para recibir avisos operativos

El Compose actual **no incluye Alertmanager ni configura otro receptor de las reglas**. La clave Brevo usada por la web no hace que Prometheus envíe correos automáticamente. Para completar esa parte se necesita:

1. Definir receptor, por ejemplo `info@mascomatch.com`.
2. Integrar y configurar Alertmanager o un servicio compatible, con secretos separados según necesidad.
3. Configurar Prometheus para enviarle sus alertas.
4. Disparar una condición de prueba controlada y comprobar recepción/resolución.

Es un paso técnico pendiente de integración, no un valor oculto de `.env.production`. No se afirma que esté resuelto en este procedimiento. [Arquitectura de alertas de Prometheus](https://prometheus.io/docs/alerting/latest/overview/).

Agregar además un monitor **fuera del VPS**, para que avise si el servidor completo cae. Puede consultar la portada y una lectura pública de API; el endpoint `/api/health` por sí solo confirma únicamente el proceso web. Configurar destino de avisos y comprobar una interrupción controlada antes de depender de ese monitor.

**Resultado esperado:** web observada desde fuera, reglas privadas consultables y notificaciones operativas recibidas cuando el receptor adicional esté integrado. Mientras falte, hay que revisar manualmente el estado y registrar esa limitación del piloto.

## 19. Criterio para abrir el piloto al público

Completar esta lista y registrar cualquier excepción antes de anunciar la URL:

- [ ] Dominio correcto y HTTPS válido.
- [ ] VPS independiente de la PC, con acceso de recuperación y firewall.
- [ ] `production_apply.py check` correcto y modelos instalados.
- [ ] Correo real recibido: confirmación, recuperación y aviso al dueño.
- [ ] Formularios, mapa, direcciones, fotos y avistamientos vinculados probados.
- [ ] Cuenta administradora exclusiva asignada y confirmada.
- [ ] Backup local y B2 recientes; bloqueo y descarga verificados.
- [ ] Clave AES almacenada fuera del VPS y simulacro de restauración correcto.
- [ ] Monitoreo exterior y receptor de alertas operativas comprobados, o limitación temporal explícita con revisión manual.
- [ ] Capacidad de disco/RAM y demoras de IA observadas en el servidor real.
- [ ] Textos `/terminos` y `/privacidad` revisados para el uso/proveedores reales; decisión de analytics resuelta.
- [ ] Condiciones del servicio de direcciones/mapas compatibles con el tráfico esperado.
- [ ] Casos públicos de prueba cerrados/retirados y avisos reales revisados.

Los aportes puntuales tienen integración con Mercado Pago, desactivada por defecto. Falta completar las credenciales, URL pública HTTPS y webhooks, probar el entorno de prueba y habilitar producción según [el procedimiento de Mercado Pago](mercado-pago-configuracion.md). Publicar la web no habilita cobros por sí solo. La eficacia de las coincidencias se evalúa con respuestas de dueños en el panel; un smoke correcto no garantiza que identifique cada animal.

Para una primera apertura controlada, invitar un grupo pequeño, revisar avisos/cola/correos a diario y ampliar la convocatoria después de observar funcionamiento, capacidad y calidad de resultados. No hay réplicas ni failover automático: la recuperación ante pérdida del VPS es manual con B2.

## 20. Operación habitual y actualizaciones

**VPS, dentro de `~/MascoMatch`, con `dc` definida:**

```sh
dc ps
dc logs --tail 80 api worker worker-ai backup caddy
docker stats --no-stream
df -h /
python3 tools/production_apply.py check
```

Revisar `/admin`, pendientes de correo, retrasos de trabajos, fecha de captura B2 y espacio. Los backups completos pueden crecer con las fotos. Con B2 caído se conservan pendientes aunque superen 14 copias; ampliar capacidad y resolver la caída antes de quedarse sin disco.

Para una actualización aprobada, primero comprobar cambios locales y revisión:

```sh
cd ~/MascoMatch
git status --short
git fetch origin
git log --oneline HEAD..origin/main
```

Si hay una modificación local, por ejemplo la regla www, integrarla con la versión aprobada antes de continuar; no descartarla automáticamente. Cuando no haya conflicto y se apruebe la revisión:

```sh
git pull --ff-only origin main
python3 tools/production_apply.py deploy --with-ai
python3 tools/production_apply.py check
```

El despliegue detiene brevemente API/workers para respaldar/migrar; coordinar esa ventana. La aceptación inicial de Gemma se conserva mediante los pesos verificados; si faltan o cambian, detenerse y revisar antes de aceptar/instalar nuevamente.

Después de modificar solo SMTP/otros secretos que carga la API:

```sh
dc up -d --no-deps --force-recreate api
```

Después de modificar secretos B2, recrear `backup` con el mismo criterio. `restart` no garantiza aplicar variables ni reemplazar montajes de archivos editados. Si cambia un valor incorporado al build, como país de búsqueda, reconstruir/desplegar la web.

Para pausar Gemma ante un problema operativo, usando el mecanismo ya implementado:

```sh
python3 tools/production_apply.py pause-ai
```

Para volver al perfil completo cuando los modelos estén instalados y se haya corregido la causa:

```sh
python3 tools/production_apply.py resume-ai
```

No ejecutar `docker compose down -v`, `docker volume prune` ni borrados generales como solución a errores: pueden eliminar datos y copias locales. Ante un despliegue fallido, conservar los volúmenes, revisar el paso y volver a ejecutar el procedimiento correspondiente. Ante pérdida real de datos, restaurar en destinos nuevos y vacíos según la guía B2; no hacer un checkout antiguo sobre un esquema nuevo como supuesto rollback.

Mantener Ubuntu/Docker y dependencias mediante cambios revisados, y repetir el simulacro cuando cambie el formato, el servidor o el tamaño de los respaldos. Para un reinicio del VPS, coordinarlo y comprobar después `dc ps`, el chequeo de aplicación y los flujos esenciales.

## Resumen: quién hace qué

| Responsable | Acciones |
| --- | --- |
| Propietario | Contratación VPS/B2, acceso a cuentas, DNS, claves en archivos privados, aceptación de términos, criterio de apertura y receptor de alertas |
| Scripts del repositorio | Generación de secretos, imágenes, migraciones, modelos, arranque, roles de base, respaldos y reintentos |
| Comprobación conjunta | HTTPS, correo real, recorridos públicos, recuperación, rendimiento y recepción de alertas |
| Integración pendiente | Receptor de alertas operativas; configuración y validación externa de Mercado Pago; proveedor de direcciones de mayor capacidad si el piloto supera la demo pública |

La siguiente acción concreta es disponer del VPS Ubuntu 24.04 amd64, su IP y acceso administrativo. Con esos datos se puede comenzar por el paso 2 sin tocar la instalación local de desarrollo.
