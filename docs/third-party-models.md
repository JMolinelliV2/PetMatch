# Modelos de terceros

Revisión de procedencia y contrato de inferencia: 15 de octubre de 2026. Los pesos se instalan mediante comandos explícitos y permanecen en volúmenes privados del servidor. No se ejecuta código de repositorios remotos ni se utiliza `trust_remote_code`.

## Pet-ReID

- Modelo: [`open-noodle/pet-recognition-base`](https://huggingface.co/open-noodle/pet-recognition-base).
- Revisión: `fa30eb7785ceb764d5c2840c4585fb89821be385`.
- Archivo: `recognition/model.onnx`, 348.108.213 bytes.
- SHA-256: `8691f5f6d0cebbd1602d21def63a34f7a58f78e08b3d4914cb81adcc2efd83f8`.
- Licencia declarada del checkpoint: Apache-2.0. Backbone DINOv2 base congelado, Apache-2.0; proyección entrenada a 512 dimensiones.
- Finalidad: señal de identidad individual para perros y gatos. No es una probabilidad ni una identificación concluyente.
- Contrato: RGB, resize directo 224×224, float32 NCHW; media ImageNet `[.485,.456,.406]`, desviación `[.229,.224,.225]`; salida `[N,512]`, normalización L2 comprobada. Se aplica un recorte previo de la mascota cuando es confiable.
- Runtime: ONNX Runtime 1.31.0 (MIT), NumPy y Pillow. Ejecución CPU local, sin descargar pesos durante peticiones.

La [ficha fijada](https://huggingface.co/open-noodle/pet-recognition-base/blob/fa30eb7785ceb764d5c2840c4585fb89821be385/README.md) declara entrenamiento de la proyección únicamente con Dogs-World (CC0) y Cat Individual Images (CC BY); DogFaceNet se utilizó solo para evaluación. Metadatos originales: [Dogs-World](https://www.kaggle.com/datasets/lextoumbourou/dogs-world) y [Cat Individual Images, Tzu-Yuan Lin](https://www.kaggle.com/datasets/timost1234/cat-individuals), CC BY 4.0. El autor declara uso comercial permitido. Se verificaron las declaraciones publicadas; no se realizó una auditoría de titularidad de cada fotografía del dataset.

MascoMatch implementa su propio adaptador del contrato ONNX. No incorpora el código AGPL de Gallery ni su entrenamiento. Tampoco incorpora MegaDescriptor, PetFace, AvitoTech o pesos con restricciones de uso no comercial. Las métricas publicadas por el autor no se presentan como precisión de MascoMatch.

## Detector RF-DETR Nano

- Exportación: [`open-noodle/rfdetr-nano`](https://huggingface.co/open-noodle/rfdetr-nano).
- Revisión: `1618db5f22919339f4347d436da8c43afaf91926`.
- Archivo: `detection/model.onnx`, 107.835.234 bytes.
- SHA-256: `21045851f3906c7d424874363fe933477fda7210bad0d7a69659fb98f8845890`.
- Licencia de código y pesos Nano: Apache-2.0, según [Roboflow RF-DETR](https://github.com/roboflow/rf-detr#license) y la ficha del exportador. No se usan variantes Plus/PML ni Ultralytics.
- Procedencia declarada: pesos COCO sin ajuste adicional. COCO distribuye anotaciones con CC BY 4.0 y sus fotografías conservan licencias de origen; MascoMatch no redistribuye ese dataset.
- Input: float32 `[1,3,384,384]`, RGB resize cuadrado y normalización ImageNet. Outputs: cajas normalizadas cx/cy/w/h `[1,300,4]` y logits `[1,300,91]`; sigmoid, índices COCO cat=17/dog=18.
- Uso: cajas con confianza ≥0,75, margen 18%; baja confianza, varios animales ambiguos, ausencia o fallo → imagen completa con motivo registrado. Runtime ONNX Runtime, CPU.

## OpenCLIP

- Modelo lógico: `ViT-B-32:openai`, 512D.
- Pesos Safetensors: [`timm/vit_base_patch32_clip_224.openai`](https://huggingface.co/timm/vit_base_patch32_clip_224.openai).
- Revisión: `a6f597a30f7b82c51704746581f9a4e41421e878`.
- Archivo: `open_clip_model.safetensors`, 605.143.284 bytes.
- SHA-256: `e6d1bd7789aa45192b3bf90570a789b478bae1b74ebcce7eddd908e83a2b7c31`.
- [OpenCLIP](https://github.com/mlfoundations/open_clip) y [CLIP](https://github.com/openai/CLIP): MIT. Conversión timm: Apache-2.0 declarada en su ficha.
- Dependencias: open_clip_torch 3.2.0, PyTorch 2.13.0 CPU, Torchvision 0.28.0 CPU; versiones transitivas fijadas en `requirements-vision.lock`.
- Uso: alternativa explícita para perros y gatos al deshabilitar Pet-ReID. No habilita otras especies. RGB orientado por EXIF, resize/center crop 224 de OpenCLIP, QuickGELU y normalización propia del modelo; vector L2.
- El dataset de entrenamiento original de CLIP no se distribuye con MascoMatch; las licencias de código/pesos no equivalen a una auditoría de derechos de sus imágenes originales.

## Gemma 3 4B

- Se mantiene `gemma3:4b`, mediante Ollama 0.35.1 local (runtime MIT). Finalidad exclusiva: extraer atributos estructurados, no identificar al individuo.
- Manifiesto OCI SHA-256: `a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a`.
- Modelo principal: `aeda25e63ebd698fab8638ffb778e68bed908b960d39d0becc650fa981609d25`, 3.338.792.448 bytes. Total de blobs: 3.338.801.804 bytes.
- Los hashes de configuración, plantilla, licencia y parámetros están fijados en `app/analysis/gemma_setup.py`; no se sigue silenciosamente una etiqueta mutable.
- Fuente: [Ollama Gemma 3](https://ollama.com/library/gemma3) y [Google Gemma 3](https://ai.google.dev/gemma/docs/core/model_card_3).
- Pesos sujetos a [Gemma Terms of Use](https://ai.google.dev/gemma/terms), versión publicada el 1 de abril de 2026, y [Prohibited Use Policy](https://ai.google.dev/gemma/prohibited_use_policy). Uso comercial condicionado al cumplimiento de esos términos; no son una licencia MIT/Apache de los pesos. Los términos incluyen servicios alojados. El instalador nuevo exige aceptación explícita; `/terminos` incorpora las restricciones y enlaces. El blob de licencia original se conserva.
- Los datos de entrenamiento y limitaciones están descritos por Google en su model card. No se entrenó ni modificó el checkpoint para esta entrega.

## Instalación e integridad

`app.embeddings.setup` descarga únicamente nombres/revisiones/rutas de la lista fija, verifica tamaño y SHA-256 y ejecuta una inferencia local de carga. `--check` no usa red. `app.analysis.gemma_setup` verifica cada blob y el manifiesto exacto; `--check` permite reutilizar la instalación existente. No se aceptan URLs ni rutas de modelos procedentes del usuario público. No se usa pickle para pesos.

Los manifiestos y este documento conservan avisos de procedencia. Para redistribuir pesos fuera del servicio alojado deben acompañarse de sus licencias y avisos correspondientes. Las dependencias del runtime conservan sus archivos de licencia instalados.

## Fotos de comprobación técnica

Las descargas opcionales del smoke usan dos fotos CC0: [Hamoma30, A lovely dog sitting on floor](https://commons.wikimedia.org/wiki/File:A_lovely_dog_sitting_on_floor.jpg) y [Kryesmin, Bangladeshi Cat](https://commons.wikimedia.org/wiki/File:Bangladeshi_Cat.jpg). Se guardan en almacenamiento temporal/ignorado. Repetir una foto solo comprueba el circuito técnico: no mide eficacia de identidad. El smoke actual utiliza únicamente perros y gatos; los escenarios históricos de otras especies ya no representan rutas de publicación admitidas.
