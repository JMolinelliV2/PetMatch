# Puesta en marcha de MascoMatch

Guía del 9 de octubre de 2026. La elección del servidor y la configuración en las cuentas externas siguen pendientes. Los precios son los anunciados en las páginas enlazadas; confirmar plazo, total anticipado, impuestos y renovación en el checkout.

## Condición del despliegue: producción fuera de la PC

La producción debe funcionar con la PC del operador apagada o sin conexión. Web, API, PostgreSQL, Redis, fotos, workers, Ollama y OpenCLIP se ejecutarán y almacenarán sus datos en el servidor contratado. En este contexto, “IA local” significa inferencia dentro de ese servidor, sin una API de IA de pago.

Las copias cifradas se exportarán a otro almacenamiento externo. La clave de recuperación se conservará en una bóveda cifrada externa separada del VPS y del destino de las copias. El correo, la búsqueda de direcciones y el monitor externo utilizarán sus respectivos servicios. Los secretos de producción se generarán y configurarán en el servidor; la PC no será un destino de respaldo ni un nodo de procesamiento.

El equipo personal podrá usarse para acceder al sitio o administrar los servicios, sin depender de él para la disponibilidad de producción. La instalación de desarrollo existente es independiente del despliegue público.

## 1. Elegir el servidor

El despliegue actual ejecuta Next.js, FastAPI, PostgreSQL con PostGIS/pgvector, Redis, almacenamiento de fotos y procesamiento local con Ollama/OpenCLIP. Se recomienda un VPS Linux x86-64 con al menos 16 GB de RAM para el piloto que incluya todos los modelos. Esta es una estimación para empezar: todavía hay que medir memoria, duración de inferencia y cola en el servidor elegido. Un VPS con CPU no ofrece la velocidad de una GPU.

| Opción | Recursos anunciados | Precio anunciado | Cuándo elegirla |
| --- | --- | --- | --- |
| [Hostinger KVM 4](https://www.hostinger.com/vps-hosting) | 4 vCPU, 16 GB RAM, 200 GB NVMe | US$12,99/mes promocional; US$28,99/mes al renovar, según el plazo mostrado | Recomendación para comenzar con un único panel y el dominio existente. |
| [Contabo Cloud VPS 8](https://contabo.com/en-us/vps/) | 8 vCPU, 24 GB RAM, 300 GB SSD | €11,20/mes efectivo durante los primeros 24 meses; tarifa de referencia €14/mes | Alternativa económica; revisar moneda, ubicación, alta, plazo y total. |
| [OVHcloud VPS-4](https://www.ovhcloud.com/en/vps/) | 8 vCores, 24 GB RAM, 200 GB NVMe | Desde US$23,37/mes en la página internacional consultada | Alternativa con más CPU/RAM; confirmar región, disponibilidad y condiciones. |

Hostinger indica que sus planes VPS se pagan por adelantado y que el precio mensual es el total dividido por el plazo. La elección debe comparar el desembolso completo. [Condiciones y precios](https://www.hostinger.com/vps-hosting).

El presupuesto inicial indicado fue **US$30 mensuales para todos los servicios**. Conviene reservar aproximadamente US$5 para respaldos externos e impuestos, dejando hasta US$20–25 para el VPS. KVM 4 entra durante la promoción; su renovación anunciada de US$28,99 puede superar el total al sumar extras. Contabo tiene una oferta efectiva para 24 meses y la moneda mostrada es EUR: confirmar el costo real en USD y el precio del período elegido. OVHcloud deja un margen menor. El dominio adquirido es un costo aparte que debe contemplarse al renovar.

Para un público inicial en Uruguay, elegir Brasil si aparece disponible. Hostinger ofrece esa región para VPS, sujeta a capacidad, y fija la ubicación durante la configuración inicial. [Ubicaciones](https://www.hostinger.com/support/1583267-where-are-hostinger-servers-located/).

Seleccionar **Ubuntu 24.04 LTS, x86-64**, con Docker Compose. El proyecto ya tiene un archivo de despliegue propio; alcanza con un sistema limpio. Un plan web para WordPress o un constructor de páginas no ejecuta este despliegue completo. El dominio puede seguir registrado y administrado en Hostinger aunque el servidor sea de otro proveedor.

### Escenario con US$80 mensuales

Con ese margen conviene priorizar CPU dedicada para el procesamiento local. Hostinger publica un sistema de créditos que permite ráfagas de CPU y reduce la capacidad cuando se agota el saldo; por eso, su cantidad de vCPU no equivale a capacidad completa de uso continuo. Esto importa si la cola de IA mantiene al procesador ocupado. [Funcionamiento oficial de los créditos](https://www.hostinger.com/support/how-cpu-credits-work-on-hostinger-vps/).

Una primera opción es **Contabo Max Performance / Cloud VDS S**: 6 núcleos virtuales dedicados, 24 GB de RAM y 180 GB NVMe. El catálogo consultado anuncia €39,20/mes efectivo para un plazo de 24 meses. Cotizar un período corto y confirmar moneda, región, alta, impuestos y renovación antes de elegir el contrato. Para el piloto se propone un costo final de servidor de hasta US$60 mensuales. [Recursos dedicados](https://contabo.com/en-us/vps-dedicated/) y [precios](https://contabo.com/en-us/pricing/).

Distribución objetivo del tope: hasta US$60 para el servidor, US$8 para la copia externa y US$12 de reserva, sumando US$80. Brevo, Geoapify y monitoreo externo pueden iniciar en sus planes gratuitos dentro de sus condiciones y cuotas; la reserva permite revisar correo pago si hace falta. Brevo Free tiene 300 envíos diarios y puede demorar correos transaccionales al agotar la cuota, de modo que hay que contar confirmaciones, recuperaciones, alertas de mascotas y avisos operativos juntos. [Límites de Brevo](https://help.brevo.com/hc/en-us/articles/208580669-FAQs-What-are-the-limits-of-the-Free-plan).

Los 24 GB son una propuesta para ejecutar el stack y los modelos actuales con más margen de memoria. La inferencia sigue siendo en CPU: medir tiempo por trabajo y demoras con fotos representativas. Más recursos no validan por sí solos la precisión del reconocimiento. Estos VPS/VDS requieren mantenimiento de la aplicación y del sistema; el precio del servidor no incluye un servicio de administración de MascoMatch.

## 2. Dominio y HTTPS

En la zona DNS que administra mascomatch.com, configurar:

| Tipo | Nombre | Valor |
| --- | --- | --- |
| A | `@` | IPv4 pública del VPS contratado |

Usar la IP del VPS nuevo, no la dirección que tenga actualmente el dominio. Revisar si existe un registro AAAA: debe corresponder al servidor elegido si se utiliza IPv6. Mantener los registros de correo y verificación del dominio. No hace falta transferir el dominio ni cambiar de proveedor de DNS para apuntarlo al VPS.

La configuración actual de Caddy atiende `mascomatch.com`. Para ofrecer también `www.mascomatch.com`, habrá que agregar su DNS y una regla de redirección/certificado en Caddy; un CNAME por sí solo no completa ese soporte.

Permitir 80/TCP y 443/TCP en el firewall del proveedor; 443/UDP es opcional para HTTP/3. Restringir SSH al acceso del operador cuando sea posible. PostgreSQL, Redis, almacenamiento y Ollama permanecen sin puertos públicos según `compose.production.yml`. Caddy obtiene y renueva HTTPS una vez que DNS apunta al servidor y los puertos están disponibles.

## 3. Brevo

La integración existente utiliza SMTP. En Brevo, abrir **SMTP & API → SMTP** y tomar el **login SMTP** y la **clave SMTP**. La API key de la pestaña API no sirve como contraseña SMTP. [Instrucciones de Brevo](https://help.brevo.com/hc/en-us/articles/7924908994450-Send-transactional-emails-using-Brevo-SMTP).

Autenticar `mascomatch.com` con los registros exactos que Brevo indique y crear el remitente `MascoMatch <avisos@mascomatch.com>`. Hay que comprobar Brevo code, DKIM y DMARC en su panel. La consulta DNS pública del 9 de octubre encontró registros SPF y DMARC existentes: revisarlos antes de agregar otros, y conservar una sola política SPF y una sola política DMARC por nombre. El estado final de autenticación debe confirmarse en Brevo. [Autenticación del dominio](https://help.brevo.com/hc/en-us/articles/12163873383186-Authenticate-your-domain-with-Brevo-Brevo-code-DKIM-DMARC).

Después de generar los archivos privados en el servidor, completar `.env.production`:

```dotenv
MAIL_DELIVERY_MODE=smtp
SMTP_HOST=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USERNAME=LOGIN_SMTP_DEL_PANEL_DE_BREVO
SMTP_FROM=MascoMatch <avisos@mascomatch.com>
SMTP_TLS_MODE=starttls
```

La clave SMTP se guarda en `.secrets/smtp_password`, mediante un editor privado en el servidor. No se introduce en el código del frontend ni en una variable `NEXT_PUBLIC_*`. `.env.production` y `.secrets/` están excluidos de Git. El login SMTP puede diferir tanto del remitente como del correo utilizado para abrir la cuenta Brevo.

Recrear la API para aplicar la configuración:

```sh
docker compose -p mascomatch --env-file .env.production -f compose.production.yml up -d --force-recreate api
```

Antes de abrir al público, comprobar en cuentas controladas: confirmación de correo, recuperación y aviso por avistamiento. En producción la cuenta del dueño debe confirmar su dirección para recibir alertas. Verificar recepción, además del estado de envío que registra el sistema.

## 4. Búsqueda de direcciones y mapas

Son dos servicios distintos:

| Servicio | Qué hace hoy | Propuesta para el piloto |
| --- | --- | --- |
| Photon | Sugiere direcciones y consulta la dirección del pin desde `/api/places`. | Mantenerlo en desarrollo; elegir un servicio con plan de producción para el despliegue público. |
| OpenStreetMap + Leaflet | Dibujan el mapa y permiten mover el pin. | Conservarlos para el piloto respetando atribución y política de uso; revisar proveedor de teselas si aumenta el tráfico. |

Se recomienda [Geoapify Free](https://www.geoapify.com/pricing/) para direcciones: 3.000 créditos diarios, sin tarjeta, disponible para producción con atribución. Una consulta de autocompletado o inversa consume un crédito; las sugerencias mientras se escribe pueden hacer varias consultas por publicación. El plan usa cuotas blandas y puede restringir cuentas que superan su uso: no debe describirse como ilimitado ni como un corte automático exacto al llegar a 3.000.

**La integración actual es compatible con Photon. Geoapify requiere un adaptador; no alcanza con cambiar `GEOCODER_BASE_URL`.** Antes de habilitarlo se debe implementar:

- Consultas desde el servidor y clave privada, sin entregarla al navegador.
- Autocompletado y consulta inversa para el pin y país del dispositivo.
- Filtro por país, prioridad de coincidencias exactas y cercanía, conservando `Place` y el flujo actual.
- Límites de solicitudes y de consumo, caché controlada y mensajes de indisponibilidad.
- Atribución a Geoapify junto a los resultados, además de OpenStreetMap.

El usuario necesita crear la cuenta gratuita y un proyecto. La clave se incorpora después a un archivo privado del servidor; la integración no debe solicitar una suscripción paga ni activar facturación automáticamente.

El mapa actual usa `tile.openstreetmap.org`: no requiere una clave, pero es un servicio de disponibilidad limitada, sin SLA. No hacer descargas masivas ni precarga, mantener el Referer y respetar caché/atribución. Un proveedor de direcciones no reemplaza automáticamente al proveedor de mapas. [Política oficial de teselas](https://operations.osmfoundation.org/policies/tiles/).

## 5. Operación: quién se entera y cómo se recupera

| Área | Ya preparado en el repositorio | Falta configurar o implementar |
| --- | --- | --- |
| HTTPS y redes | Caddy, certificados y servicios privados. | VPS, DNS y firewall. |
| Respaldos | Copia cifrada diaria de base y fotos; retención de 14 copias; verificación y restauración a destinos vacíos. | Copia automática fuera del VPS y un ensayo de recuperación allí. |
| Métricas internas | Prometheus y reglas de disponibilidad, cola demorada, fallos de correo y respaldo atrasado. | Destino de avisos: conectar Alertmanager al correo privado del operador. |
| Caída completa del VPS | Endpoint web de salud y aplicación pública para consultar desde fuera. | Monitor externo que siga funcionando si el VPS se apaga. |
| Capacidad | Procesamiento en cola, modelos locales y límites de servicios. | Medir memoria, CPU, espacio y demora en el VPS elegido; añadir alertas de disco/recursos. |
| Mantenimiento | Imágenes versionadas y CI con auditorías de dependencias. | Rutina de actualizaciones, respaldo previo y procedimiento de vuelta a una versión anterior. |

### Avisos internos

Prometheus detecta problemas; Alertmanager agrupa y entrega los avisos. Su configuración debe usar un archivo privado para la contraseña SMTP y para el correo del operador. Agrupar/repetir avisos con moderación evita consumir toda la cuota de Brevo. El correo personal del operador se configura solo en los archivos privados y en el servicio de monitoreo; no en el sitio ni en el repositorio. Esta conexión todavía no está implementada en el Compose actual. [Alertmanager](https://prometheus.io/docs/alerting/latest/alertmanager/).

### Monitor externo

Para el MVP personal o sin fines de lucro, [UptimeRobot Free](https://uptimerobot.com/pricing/) anuncia 50 monitores y consultas cada 5 minutos sin tarjeta. Configurar monitoreo HTTPS de `https://mascomatch.com/` y `https://mascomatch.com/api/health`, con avisos al correo privado del operador y avisos de recuperación. Confirmar las condiciones del plan si el proyecto cambia a uso comercial. Una caída puede demorar varios minutos en detectarse con ese intervalo.

Un monitor que corre dentro del mismo VPS no puede avisar por sí mismo cuando se apaga todo el servidor. Los avisos de los avistamientos a los dueños y los avisos operativos al operador cumplen funciones diferentes.

### Copia fuera del servidor

Elegir un almacenamiento de respaldo con costo acotado, por ejemplo un [Storage Box](https://www.hetzner.com/storage/storage-box/) con SFTP. El Storage Box tiene que contratarse y configurarse aparte; el precio depende del checkout/región. Preparar una transferencia diaria entre el VPS y ese almacenamiento de las copias ya cifradas, con credencial dedicada, y avisar si no se exporta la copia esperada. No borrar el destino durante la sincronización. La PC personal no participa en esta transferencia; el ensayo de recuperación se realiza en otro entorno remoto aislado.

Guardar una copia de `backup_key` en una bóveda cifrada externa, fuera del VPS y fuera del mismo almacenamiento de respaldos, y comprobar su recuperación. La copia cifrada necesita esa clave para recuperarse. Un snapshot del proveedor o un respaldo en el disco del VPS no sustituye esta exportación.

El límite inicial del sistema de respaldo es 1 GB por archivo descifrado y 20.000 fotos; ampliar esa capacidad antes de superarla. El ensayo de restauración debe comprobar cuentas, avisos, fotos y acceso sin sobrescribir la instalación vigente.

## 6. Orden de despliegue

1. Elegir VPS, plazo y región; obtener IP y acceso SSH privado.
2. Instalar Docker Compose y clonar el repositorio en el servidor.
3. Generar `.env.production` y `.secrets/` allí, sin copiarlos al repositorio.
4. Configurar SMTP y DNS del sitio y de Brevo.
5. Iniciar la aplicación en modo producción; comprobar HTTPS y los flujos públicos/privados.
6. Instalar los modelos, habilitar IA/embeddings y medir una cola con ejemplos controlados.
7. Integrar el proveedor elegido para direcciones.
8. Activar monitoreo interno, entrega de avisos y monitor externo.
9. Exportar un respaldo y recuperar una copia aislada.
10. Abrir un piloto pequeño y recoger resultados de coincidencias reales.

Comandos base, ejecutados en el VPS después de instalar Docker y Python:

```sh
git clone https://github.com/JMolinelliV2/MascoMatch.git
cd MascoMatch
python3 tools/production_init.py --domain mascomatch.com
docker compose -p mascomatch --env-file .env.production -f compose.production.yml up -d --build
```

El generador rechaza sobrescribir secretos existentes. Para instalación de modelos, respaldos y restauración, seguir [la guía de producción](production.md). Los avisos locales y sus fotos se conservan: una instalación nueva en el VPS no migra esos datos automáticamente. Si deben conservarse en el sitio público, preparar una migración antes del lanzamiento.

## Datos que faltan para aplicar la configuración externa

- Presupuesto mensual y monto que se puede pagar por adelantado.
- VPS elegido, región e IP pública.
- Login SMTP, clave SMTP guardada privadamente y estado de autenticación de Brevo.
- Cuenta/proveedor de direcciones elegido.
- Correo privado para avisos operativos y destino para los respaldos externos.

Esta guía organiza la puesta en marcha. No significa que el dominio esté sirviendo la aplicación ni que los servicios externos hayan sido activados.
