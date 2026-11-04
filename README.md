# Simulación FIFO de una oficina de pagos

Simulador en Python de una cola FIFO con un servidor. Ajusta distribuciones a tablas de frecuencias, genera tiempos mediante transformada inversa y analiza la espera media de réplicas de 100 clientes.

## Requisitos e instalación

Python 3.10 o posterior. El programa y sus pruebas usan exclusivamente la biblioteca estándar: no requieren paquetes externos ni ProModel, NumPy o SciPy.

```powershell
git clone https://github.com/iTzManix/simulacion_fifo.git
cd simulacion_fifo
py -3 -m venv .venv
.\.venv\Scripts\python.exe simulacion.py
```

No es necesario activar el entorno virtual. En sistemas donde no exista `py`, use `python -m venv .venv`. El archivo `requirements.txt` no contiene dependencias externas; ejecutar `python -m pip install -r requirements.txt` es opcional.

En Linux o macOS:

```bash
python3 -m venv .venv
.venv/bin/python simulacion.py
```

## Uso

```powershell
.\.venv\Scripts\python.exe simulacion.py --help
.\.venv\Scripts\python.exe simulacion.py --semilla 12345 --salida resultados_otra_semilla
.\.venv\Scripts\python.exe simulacion.py --precision 0.05 --salida resultados_precision_5
.\.venv\Scripts\python.exe simulacion.py --empirica --salida resultados_empiricos
.\.venv\Scripts\python.exe -m unittest -v
```

El valor de precisión es una proporción: `0.10` equivale al 10%. La semilla predeterminada es `20261103`. Usar de nuevo la misma carpeta de salida reemplaza los resultados anteriores.

## Modelo

- Una cola FIFO y un servidor, sin abandonos ni interrupciones.
- 100 clientes por réplica; sistema inicialmente vacío y servidor libre.
- Primera llegada después del primer intervalo generado; atención hasta la salida del cliente 100.
- Indicador: promedio de las 100 esperas en cola, incluidos los ceros.
- Cinco réplicas piloto y un lote independiente de confirmación con tamaño fijado a partir del piloto.
- Intervalo bilateral aproximado del 95%; objetivo predeterminado de error relativo máximo del 10%.

Se evalúan uniforme discreta, geométrica positiva, Poisson desplazada y binomial desplazada. Se agrupan esperados pequeños y se reestima el parámetro para la prueba chi-cuadrado. La selección usa el menor AICc entre familias teóricas no rechazadas al 5%. Con las tablas incorporadas, se eligen `1 + Poisson(1.5)` para intervalos entre llegadas y `1 + Binomial(4, 0.475)` para servicio. La opción `--empirica` usa las frecuencias directamente.

Los tiempos son minutos. Las medias de entrada de 2.5 y 2.9 dan una carga ofrecida de 1.16: las esperas estimadas describen un experimento terminante de 100 clientes, no un régimen estacionario. La precisión Monte Carlo no cuantifica la incertidumbre del ajuste de entradas ni valida por sí sola el sistema real.

## Archivos y salidas

| Archivo | Contenido |
| --- | --- |
| `simulacion.py` | Ajuste, generación, simulación e inferencia |
| `test_simulacion.py` | Siete pruebas, incluida una referencia independiente por eventos |
| `manual.md` | Comandos e interpretación de las salidas |
| `requirements.txt` | Declaración de que no existen dependencias externas |
| `.gitignore` | Lista de archivos permitidos para publicación |

Cada ejecución crea `replicas.csv`, `clientes.csv`, `ajustes.csv`, `distribuciones.csv`, `resumen.json` y `demostracion.txt` dentro de la carpeta de salida. Estos archivos se generan localmente y no se incluyen en el repositorio. Consulte [manual.md](manual.md) para interpretar cada campo.
