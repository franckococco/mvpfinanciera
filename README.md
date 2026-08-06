# Finan — MVP Factoring & BNPL

Plataforma web en **Streamlit** para operar:

- **Factoring**: adelanto de cupones de tarjeta (neto, comisión, TNA/TEA)
- **BNPL**: créditos de consumo en comercios (cronograma + pagaré WhatsApp)
- **Dashboard**: cartera activa, comisiones del mes y vencimientos

## Estructura

```
finan/
├── app.py                 # Entrada + navegación + dashboard
├── requirements.txt
└── modules/
    ├── database.py        # Persistencia SQLite local
    ├── factoring.py       # Adelanto de cupones
    ├── bnpl.py            # Créditos BNPL
    └── ui.py              # Estilos y componentes visuales
```

## Requisitos

- Python 3.10+

## Instalación y uso

```bash
pip install -r requirements.txt
streamlit run app.py
```

La base de datos local `finan.db` se crea automáticamente al iniciar (no se versiona).
