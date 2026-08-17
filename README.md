# Finan — préstamo al comercio y crédito al cliente

Plataforma web en **Streamlit** para operar dos productos:

- **Préstamo al comercio**: se entrega un monto de una vez y se cobra un porcentaje de las ventas electrónicas del local.
- **Crédito al cliente del comercio**: el cliente compra en el local y paga en cuotas (red cerrada del comercio, no tarjeta de red abierta).
- **Trazabilidad**: expediente, contrato, pagaré, firma **Signatura Flex**, checklist y desembolso.

El adelanto de cupones (factoring) quedó fuera del producto.

## Estructura

```
finan/
├── app.py
├── requirements.txt
└── modules/
    ├── database.py
    ├── rbf_engine.py
    ├── rbf_ui.py
    ├── bnpl.py
    ├── traceability.py
    ├── signatura.py
    ├── documents.py
    ├── checklist.py
    ├── legajo.py
    ├── trazabilidad_ui.py
    └── ui.py
```

## Requisitos

- Python 3.10+
- Cuenta [Signatura Flex](https://signatura.co/flex-plan) + API key en [connect.signatura.co](https://connect.signatura.co)

## Instalación y uso

```bash
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\streamlit run app.py
```

1. **Trazabilidad → Signatura / Config**: pegá la API key (o `SIGNATURA_API_KEY`).
2. Registrá un préstamo al comercio o un crédito al cliente: se abre el expediente en `borrador`.
3. Trazabilidad: PDF → enviar a firmar → sincronizar → checklist → desembolsar.
4. Cobros: barridos del préstamo y cuotas del cliente se registran a mano (integración con procesadora después).

La base `finan.db` se crea automáticamente (no se versiona).
