# Descripciones escritas por las personas

El campo de descripción de los formularios guarda texto escrito por la persona.
Color, tamaño y zona se guardan en sus campos y no se añaden automáticamente a la
descripción. La información adicional escrita en reportes generales se conserva
como un párrafo de texto, sin etiquetas generadas por el sistema.

La migración **0029_description_format** agrega `description_format` a avisos y
observaciones, sin modificar el texto que ya estaba guardado:

- `USER_TEXT`: texto ingresado o editado manualmente. El editor lo conserva tal
  cual, aunque incluya frases como “Zona:” o “Color principal:”.
- `LEGACY`: registros anteriores. El editor reconoce el bloque final que añadía
  el formulario antiguo —color, tamaño y zona— y conserva los párrafos escritos
  por la persona. Las notas adicionales se conservan sin el prefijo automático.
- `SYSTEM`: texto contextual de un avistamiento breve vinculado, creado sin un
  campo de descripción. El editor presenta un campo opcional vacío.

Al guardar una edición manual, el formato pasa a `USER_TEXT`. Si se deja vacía
la descripción opcional de un avistamiento vinculado, el servidor conserva su
contexto automático como `SYSTEM`; esto no obliga a agregar detalles para corregir
la fecha, ubicación o fotos. Los reportes generales siguen requiriendo descripción.

Los textos históricos permanecen intactos hasta que su autor guarda una edición.
No se reescriben resultados de IA ni se invalidan análisis por el mero cambio de
esquema. La comparación conserva acceso a las características estructuradas y a
la ubicación por los mecanismos existentes.
