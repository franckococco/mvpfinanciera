# Finan — MVP Factoring, RBF & BNPL

Plataforma web en **Streamlit** para operar:

- **Factoring**: adelanto de cupones (comisión, TNA/TEA, mercado, Signatura)
- **Adelanto de Flujo (RBF)**: crédito al comercio cobrado por barridos (francés/plana)
- **BNPL**: créditos de consumo en comercios
- **Trazabilidad**: expediente + audit log + firma **Signatura Flex**

## Estructura

```
finan/
├── app.py
├── requirements.txt
└── modules/
    ├── database.py
    ├── factoring.py
    ├── market_rates.py
    ├── rbf_engine.py
    ├── rbf_ui.py
    ├── credito_comercio.py   # legado simple
    ├── bnpl.py
    ├── traceability.py
    ├── signatura.py
    ├── documents.py
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
2. Factoring / RBF / BNPL: registran expediente en `borrador`.
3. Trazabilidad: PDF → Signatura → sync → desembolsar.
4. RBF v1: barridos se registran manualmente (integración procesadora después).

La base `finan.db` se crea automáticamente (no se versiona).
