# Logging

Usar siempre `log_message()` de `shared.logger`, nunca `print()` ni `logging` directo.

```python
from shared.logger import log_message

# Sin clase
log_message("Mensaje", level="INFO")

# Dentro de método de clase — pasar func= siempre
log_message("Mensaje", level="ERROR", func=self.mi_metodo)
```

- `log_message()` incluye `traceback.format_exc()` en cada entrada — intencional para stack completo
- Pasar `func=` dentro de métodos de clase para trazabilidad correcta
- `level`: `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`
- Usar `extra_data={}` para datos estructurados adicionales
