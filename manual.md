# Manual de uso

## 1. Abrir el programa

Instale Python 3.10 o posterior si todavía no está disponible. Abra PowerShell o una terminal en la carpeta que contiene `simulacion.py`. Puede escribir `powershell` en la barra de direcciones del Explorador de archivos y pulsar Enter.

Compruebe la instalación con `python --version`. Si Windows utiliza el lanzador `py`, reemplace `python` por `py` en los comandos.

## 2. Ejecutar el ejercicio

```powershell
python simulacion.py
```

Se requiere Python 3.10 o posterior. No se requiere internet ni instalar paquetes para simular. El programa realiza estos pasos:

1. Calcula medias, frecuencias y acumuladas de los datos.
2. Ajusta uniforme discreta, geométrica positiva, Poisson desplazada y binomial desplazada; conserva la empírica como referencia.
3. Agrupa categorías con frecuencia esperada pequeña y reestima el parámetro con la verosimilitud agrupada para la prueba chi-cuadrado. Para simular y comparar AICc utiliza la estimación de la tabla original.
4. Selecciona el menor AICc entre las familias teóricas no rechazadas.
5. Ejecuta cinco réplicas iniciales con semillas diferentes y calcula un IC de Student del 95%.
6. Planifica una muestra nueva con el t y la desviación del piloto y ejecuta ese número fijo de réplicas independientes. Las cinco iniciales no se mezclan con la confirmación.
7. Informa si la precisión observada alcanza el objetivo. Nunca oculta un incumplimiento ni repite lotes hasta obtener un resultado favorable.

La ejecución termina cuando se exportan los resultados. No necesita cerrar una ventana gráfica.

## 3. Leer los resultados

| Archivo | Cómo utilizarlo |
| --- | --- |
| `demostracion.txt` | Salida de la ejecución: primeros uniformes, tres clientes, piloto, IC y precisión |
| `distribuciones.csv` | Frecuencias, probabilidades y acumuladas empíricas y del modelo seleccionado |
| `ajustes.csv` | Parámetros, AICc, agrupaciones, observados, esperados, gl, chi-cuadrado y valor p |
| `replicas.csv` | Una fila por réplica; etapa, semilla, media y máximo de espera, utilización y otras medidas |
| `clientes.csv` | Una fila por cliente con los dos uniformes, tiempos y espera; permite reconstruir cada réplica |
| `resumen.json` | Resultados completos para procesarlos con otro programa |

Los CSV usan coma como separador y punto decimal; incluyen BOM UTF-8 para conservar las tildes. Si Excel muestra una sola columna, use **Datos > Desde texto/CSV** y elija coma como delimitador y configuración regional con punto decimal.

Todas las duraciones están en minutos. `espera` es `inicio - llegada`; `en_sistema` incluye el servicio. `utilizacion` es tiempo ocupado dividido entre el tiempo desde t=0 hasta la última salida. `cola_media` es el área de la cola dividida entre ese mismo horizonte; no es el promedio de colas vistas por los clientes. `cola_maxima` excluye a quien ya está siendo atendido.

`error_relativo` en JSON es una proporción: 0.10 equivale al 10%. Se calcula como semiamplitud del IC dividida entre la media. El IC final se construye exclusivamente con las medias de la etapa `confirmacion`, no con clientes tratados como observaciones independientes.

## 4. Cambiar la semilla o la precisión

```powershell
python simulacion.py --semilla 12345 --salida resultados_otra_semilla
python simulacion.py --precision 0.05 --salida resultados_precision_5
python simulacion.py --help
```

Con la misma semilla, parámetros y versión compatible de Python se reproducen los resultados. Cambiarla altera las llegadas, servicios y esperas individuales. Las frecuencias de entrada, el criterio de selección, las condiciones y las medias poblacionales del modelo permanecen iguales. Las medias simuladas fluctúan.

La semilla del piloto es `semilla_base + j`, j=0,...,4. La confirmación empieza en `semilla_base + 1000000`, aumentando uno por réplica. Se usa `random.Random` de Python (Mersenne Twister) y se intercalan llegada y servicio para cada cliente. Semillas distintas son una separación práctica de corridas, no una demostración matemática de independencia entre flujos.

Una precisión más exigente aumenta el costo aproximadamente con el inverso del cuadrado del error. El programa limita la planificación a 100000 réplicas. Si una ejecución no cumple, la salida lo indica; debe planificar un experimento adicional y explicar su diseño antes de usar un nuevo IC.

## 5. Comparar con entradas empíricas

```powershell
python simulacion.py --empirica --salida resultados_empiricos
```

Esta opción usa directamente las frecuencias del enunciado y sus acumuladas, sin sustituir los datos ni cambiar la condición FIFO. Es un análisis de sensibilidad; los resultados se guardan por separado. La selección de familias en `ajustes.csv` sigue siendo informativa, pero `resumen.json` indica que la ejecución empleó las empíricas.

El experimento mantiene un servidor y 100 clientes por réplica. Cambiar esas condiciones requiere modificar y verificar el modelo.

## 6. Verificar el programa y resolver errores

```powershell
python -m unittest -v
```

Las pruebas verifican cuantiles de Student, colas chi-cuadrado, resultados calculados a mano, una simulación independiente por eventos, conservación del tiempo, frontera de la inversa, masa de la cola Poisson, reproducibilidad y archivos exportados.

Si aparece «python no se reconoce», revise la instalación o use `py`. Si la terminal representa mal las tildes, consulte los archivos UTF-8 o ejecute `chcp 65001` antes del comando.

Usar la misma carpeta de salida reemplaza los archivos de una ejecución anterior. Para conservar experimentos, elija un nombre diferente con `--salida`.
