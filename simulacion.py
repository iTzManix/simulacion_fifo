"""Escenario 6: ajuste de entradas y simulación FIFO, solo biblioteca estándar.

Ejecutar: python simulacion.py --salida resultados
Las funciones no escriben archivos al importar este módulo.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

TIEMPOS = (1, 2, 3, 4, 5)
FRECUENCIAS = {"llegadas": (10, 20, 10, 5, 5), "servicio": (5, 15, 15, 10, 5)}
CANDIDATOS = ("uniforme", "geometrica", "poisson_desplazada", "binomial_desplazada", "empirica")


def beta_regularizada(x: float, a: float, b: float) -> float:
    """I_x(a,b), fracción continua de Lentz; usada para Student t."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    if x > (a + 1) / (a + b + 2):
        return 1 - beta_regularizada(1 - x, b, a)
    qab, qap, qam = a + b, a + 1, a - 1
    tiny = 1e-300
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 501):
        aa = m * (b - m) * x / ((qam + 2*m) * (a + 2*m))
        d, c = 1 + aa*d, 1 + aa/c
        d = 1 / (d if abs(d) > tiny else tiny)
        c = c if abs(c) > tiny else tiny
        h *= d*c
        aa = -(a + m)*(qab + m)*x / ((a + 2*m)*(qap + 2*m))
        d, c = 1 + aa*d, 1 + aa/c
        d = 1 / (d if abs(d) > tiny else tiny)
        c = c if abs(c) > tiny else tiny
        delta = d*c
        h *= delta
        if abs(delta - 1) < 3e-14:
            factor = math.exp(math.lgamma(a+b)-math.lgamma(a)-math.lgamma(b)
                              + a*math.log(x)+b*math.log1p(-x))
            return factor*h/a
    raise ArithmeticError("No convergió la beta incompleta")


def t_cdf(x: float, gl: int) -> float:
    if gl < 1:
        raise ValueError("Los grados de libertad deben ser positivos")
    tail = 0.5*beta_regularizada(gl/(gl+x*x), gl/2, 0.5)
    return 1-tail if x >= 0 else tail


@lru_cache(maxsize=512)
def t_critico(gl: int, confianza: float = 0.95) -> float:
    if gl < 1 or not 0 < confianza < 1:
        raise ValueError("Grados de libertad o confianza inválidos")
    objetivo = (1+confianza)/2
    lo, hi = 0.0, 1.0
    while t_cdf(hi, gl) < objetivo:
        hi *= 2
    for _ in range(70):
        mid = (lo+hi)/2
        if t_cdf(mid, gl) < objetivo:
            lo = mid
        else:
            hi = mid
    return (lo+hi)/2


def chi_supervivencia(x: float, gl: int) -> float:
    """Cola chi-cuadrado para gl enteros; recurrencia gamma semientera."""
    if x < 0 or gl < 1:
        raise ValueError("Chi-cuadrado requiere x >= 0 y gl >= 1")
    z = x/2
    a = 1.0 if gl % 2 == 0 else 0.5
    q = math.exp(-z) if a == 1 else math.erfc(math.sqrt(z))
    while a < gl/2:
        q += 0 if z == 0 else math.exp(a*math.log(z)-z-math.lgamma(a+1))
        a += 1
    return min(1.0, max(0.0, q))


def maximizar(funcion, lo: float, hi: float) -> float:
    """Sección áurea para las verosimilitudes uniparamétricas del ejercicio."""
    r = (math.sqrt(5)-1)/2
    a, b = hi-r*(hi-lo), lo+r*(hi-lo)
    fa, fb = funcion(a), funcion(b)
    for _ in range(110):
        if fa > fb:
            hi, b, fb = b, a, fa
            a = hi-r*(hi-lo)
            fa = funcion(a)
        else:
            lo, a, fa = a, b, fb
            b = lo+r*(hi-lo)
            fb = funcion(b)
    return (lo+hi)/2


def media_datos(frecuencias) -> float:
    return sum(x*f for x, f in zip(TIEMPOS, frecuencias))/sum(frecuencias)


def parametro_mle(nombre: str, frecuencias):
    media = media_datos(frecuencias)
    return {"uniforme": None, "geometrica": 1/media,
            "poisson_desplazada": media-1,
            "binomial_desplazada": (media-1)/4,
            "empirica": None}[nombre]


def probabilidades(nombre: str, parametro, frecuencias) -> list[float]:
    """Probabilidades de 1,...,5. La masa restante NO se elimina."""
    if nombre == "uniforme":
        return [0.2]*5
    if nombre == "empirica":
        return [f/sum(frecuencias) for f in frecuencias]
    if nombre == "geometrica":
        return [parametro*(1-parametro)**i for i in range(5)]
    if nombre == "poisson_desplazada":
        return [math.exp(-parametro)*parametro**i/math.factorial(i) for i in range(5)]
    if nombre == "binomial_desplazada":
        return [math.comb(4, i)*parametro**i*(1-parametro)**(4-i) for i in range(5)]
    raise ValueError(f"Distribución desconocida: {nombre}")


def masas_seis(nombre, parametro, frecuencias):
    p = probabilidades(nombre, parametro, frecuencias)
    return p + [max(0.0, 1-sum(p))]


def agrupar(p, n=50):
    """Agrupa categorías adyacentes según E, sin consultar observados.

    La sexta categoría representa 6 o más y conserva toda la cola.
    """
    grupos, actual, esperado = [], [], 0.0
    for i, prob in enumerate(p):
        actual.append(i)
        esperado += n*prob
        if esperado >= 5-1e-10:
            grupos.append(actual)
            actual, esperado = [], 0.0
    if actual:
        if grupos:
            grupos[-1].extend(actual)
        else:
            grupos.append(actual)
    return grupos


def etiqueta_grupo(g):
    return ",".join("6+" if i == 5 else str(i+1) for i in g)


def analizar_ajustes():
    filas = []
    for variable, f in FRECUENCIAS.items():
        n = sum(f)
        for nombre in CANDIDATOS:
            par = parametro_mle(nombre, f)
            p = masas_seis(nombre, par, f)
            k = 4 if nombre == "empirica" else (0 if nombre == "uniforme" else 1)
            ll = sum(o*math.log(prob) for o, prob in zip(f, p))
            aicc = -2*ll+2*k+2*k*(k+1)/(n-k-1)
            grupos = agrupar(p, n)
            observado = list(f)+[0]
            par_agrupado = par
            # Se reestima con la verosimilitud de las categorías agrupadas,
            # de acuerdo con la condición de la aproximación chi-cuadrado.
            if k == 1:
                def loglike(theta):
                    probs = masas_seis(nombre, theta, f)
                    return sum(sum(observado[i] for i in g)*math.log(max(1e-300, sum(probs[i] for i in g))) for g in grupos)
                par_agrupado = maximizar(loglike, 1e-7, 15.0 if nombre == "poisson_desplazada" else 1-1e-7)
            p_test = masas_seis(nombre, par_agrupado, f)
            os = [sum(observado[i] for i in g) for g in grupos]
            es = [n*sum(p_test[i] for i in g) for g in grupos]
            gl = len(grupos)-1-k
            aplicable = gl > 0 and min(es) >= 5-1e-8
            chi = sum((o-e)**2/e for o, e in zip(os, es)) if aplicable else None
            valor_p = chi_supervivencia(chi, gl) if aplicable else None
            filas.append(dict(variable=variable, modelo=nombre, parametro_mle=par,
                              parametro_agrupado=par_agrupado, parametros=k, log_verosimilitud=ll,
                              aicc=aicc, grupos=[etiqueta_grupo(g) for g in grupos],
                              observadas=os, esperadas=es, gl=gl, chi2=chi, valor_p=valor_p,
                              aplicable=aplicable, no_rechazado=aplicable and valor_p >= .05))
    return filas


def seleccionar(ajustes):
    """Menor AICc entre familias teóricas no rechazadas al 5%."""
    seleccion = {}
    for variable in FRECUENCIAS:
        validos = [a for a in ajustes if a['variable'] == variable and a['modelo'] != 'empirica' and a['no_rechazado']]
        seleccion[variable] = min(validos, key=lambda a: a['aicc'])['modelo'] if validos else 'empirica'
    return seleccion


def inversa(u: float, nombre: str, frecuencias) -> int:
    """Inversa generalizada F^-1(u); u=0 se extiende al menor valor."""
    if not 0 <= u < 1:
        raise ValueError("El uniforme debe pertenecer a [0,1)")
    par = parametro_mle(nombre, frecuencias)
    if nombre == 'poisson_desplazada':
        valor, prob = 1, math.exp(-par)
        acumulada = prob
        while u > acumulada:
            prob *= par/valor
            valor += 1
            nueva = acumulada+prob
            if nueva == acumulada:
                raise ArithmeticError('Precisión insuficiente en la cola de Poisson')
            acumulada = nueva
        return valor
    if nombre == 'geometrica':
        return 1 if u == 0 else math.ceil(math.log1p(-u)/math.log1p(-par))
    acumulada = 0.0
    for valor, prob in enumerate(probabilidades(nombre, par, frecuencias), 1):
        acumulada += prob
        if u <= acumulada:
            return valor
    return 5  # Solo distribuciones de soporte finito; compensa redondeo final.


@dataclass
class Cliente:
    cliente: int
    u_llegada: float
    u_servicio: float
    entre_llegadas: int
    servicio: int
    llegada: int
    inicio: int
    fin: int
    espera: int
    en_sistema: int
    ocio_previo: int


def trayectoria(intervalos, servicios, uniformes=None):
    if len(intervalos) != len(servicios) or not intervalos:
        raise ValueError('Se requieren listas no vacías de igual longitud')
    llegada, fin_anterior, clientes = 0, 0, []
    for i, (a, s) in enumerate(zip(intervalos, servicios)):
        if a <= 0 or s <= 0:
            raise ValueError('Los tiempos deben ser positivos')
        llegada += a
        inicio = max(llegada, fin_anterior)
        u, v = uniformes[i] if uniformes else (0.0, 0.0)
        clientes.append(Cliente(i+1, u, v, a, s, llegada, inicio, inicio+s,
                                inicio-llegada, inicio+s-llegada, max(0, llegada-fin_anterior)))
        fin_anterior = inicio+s
    return clientes


def simular(semilla: int, n: int, modelos):
    if n < 1:
        raise ValueError('Se requiere al menos un cliente')
    rng = random.Random(semilla)
    uniformes = [(rng.random(), rng.random()) for _ in range(n)]
    intervalos = [inversa(u, modelos['llegadas'], FRECUENCIAS['llegadas']) for u, _ in uniformes]
    servicios = [inversa(v, modelos['servicio'], FRECUENCIAS['servicio']) for _, v in uniformes]
    return trayectoria(intervalos, servicios, uniformes)


def metricas(clientes):
    fin = clientes[-1].fin
    espera = [c.espera for c in clientes]
    # La cola contiene solo clientes que han llegado pero no iniciaron servicio.
    # En empate, sale de la cola antes de ingresar otro cliente.
    eventos = sorted([(c.llegada, 1) for c in clientes if c.espera > 0]
                     + [(c.inicio, -1) for c in clientes if c.espera > 0])
    cola, max_cola = 0, 0
    for _, cambio in eventos:
        cola += cambio
        max_cola = max(max_cola, cola)
    return dict(clientes=len(clientes), espera_media=statistics.mean(espera),
                espera_maxima=max(espera), proporcion_espera=sum(w > 0 for w in espera)/len(espera),
                servicio_medio=statistics.mean(c.servicio for c in clientes),
                intervalo_medio=statistics.mean(c.entre_llegadas for c in clientes),
                tiempo_sistema_medio=statistics.mean(c.en_sistema for c in clientes),
                utilizacion=sum(c.servicio for c in clientes)/fin, fin=fin,
                cola_maxima=max_cola, cola_media=sum(espera)/fin,
                espera_primera_mitad=statistics.mean(espera[:len(espera)//2] or espera),
                espera_segunda_mitad=statistics.mean(espera[len(espera)//2:] or espera))


def resumen_estadistico(valores, confianza=.95):
    if len(valores) < 2:
        raise ValueError('El intervalo requiere al menos dos réplicas')
    n, media, s = len(valores), statistics.mean(valores), statistics.stdev(valores)
    t = t_critico(n-1, confianza)
    h = t*s/math.sqrt(n)
    return dict(replicas=n, media=media, desviacion=s, t=t, semiamplitud=h,
                inferior=media-h, superior=media+h,
                error_relativo=h/abs(media) if media != 0 else None)


def planificar(piloto, precision):
    if piloto['media'] <= 0:
        raise ValueError('La precisión relativa no está definida para una media nula')
    objetivo = precision*piloto['media']
    conservador = max(5, math.ceil((piloto['t']*piloto['desviacion']/objetivo)**2))
    iterativo = 5
    while t_critico(iterativo-1)*piloto['desviacion']/math.sqrt(iterativo) > objetivo:
        iterativo += 1
        if iterativo > 100000:
            raise ValueError('La planificación excede 100000 réplicas')
    return dict(objetivo_absoluto=objetivo, n_con_t_piloto=conservador,
                n_con_t_actualizado=iterativo, n_confirmacion=conservador)


def guardar_csv(ruta, filas):
    if not filas:
        return
    with ruta.open('w', newline='', encoding='utf-8-sig') as archivo:
        writer = csv.DictWriter(archivo, fieldnames=list(filas[0]))
        writer.writeheader()
        writer.writerows(filas)


def ejecutar(salida: Path, semilla=20261103, precision=.10, modelos_forzados=None):
    if not 0 < precision < 1:
        raise ValueError('La precisión debe estar entre 0 y 1')
    salida.mkdir(parents=True, exist_ok=True)
    ajustes = analizar_ajustes()
    modelos = modelos_forzados or seleccionar(ajustes)
    replicas, trazas = [], []

    def lote(etapa, semillas):
        filas = []
        for j, seed in enumerate(semillas, 1):
            clientes = simular(seed, 100, modelos)
            fila = dict(etapa=etapa, replica=j, semilla=seed, **metricas(clientes))
            filas.append(fila)
            for c in clientes:
                trazas.append(dict(etapa=etapa, replica=j, semilla=seed, **asdict(c)))
        replicas.extend(filas)
        return filas

    piloto = lote('piloto', range(semilla, semilla+5))
    estad_piloto = resumen_estadistico([r['espera_media'] for r in piloto])
    plan = planificar(estad_piloto, precision)
    # Tamaño fijado antes de ver la confirmación. No se detiene al primer éxito.
    n = plan['n_confirmacion']
    if n > 100000:
        raise ValueError('Demasiadas réplicas planificadas; revise la precisión')
    confirmacion = lote('confirmacion', range(semilla+1000000, semilla+1000000+n))
    estad_final = resumen_estadistico([r['espera_media'] for r in confirmacion])
    datos = {v: dict(n=sum(f), media=media_datos(f),
                    varianza_empirica=sum(fi*(x-media_datos(f))**2 for x, fi in zip(TIEMPOS, f))/sum(f),
                    varianza_muestral=sum(fi*(x-media_datos(f))**2 for x, fi in zip(TIEMPOS, f))/(sum(f)-1))
             for v, f in FRECUENCIAS.items()}
    resumen = dict(modelos=modelos, datos=datos, ajustes=ajustes, piloto=estad_piloto,
                   plan=plan, confirmacion=estad_final, precision=precision,
                   cumple=estad_final['error_relativo'] is not None and estad_final['error_relativo'] <= precision,
                   total_replicas=5+n, semilla_base=semilla,
                   condiciones=dict(clientes=100, confianza=.95, servidores=1, disciplina='FIFO',
                                    primera_llegada='A1 = primer intervalo sorteado',
                                    horizonte='desde t=0 hasta salida del cliente 100',
                                    indicador='promedio de las 100 esperas, incluidos ceros'))
    guardar_csv(salida/'replicas.csv', replicas)
    guardar_csv(salida/'clientes.csv', trazas)
    filas_ajuste = [{**a, 'grupos': '; '.join(a['grupos']),
                     'observadas': '; '.join(map(str, a['observadas'])),
                     'esperadas': '; '.join(f'{x:.10f}' for x in a['esperadas'])} for a in ajustes]
    guardar_csv(salida/'ajustes.csv', filas_ajuste)
    cdf_filas = []
    for variable, f in FRECUENCIAS.items():
        acumulada_e, acumulada_m = 0., 0.
        nombre = modelos[variable]
        probs = masas_seis(nombre, parametro_mle(nombre, f), f)
        for i, p in enumerate(probs):
            pe = f[i]/sum(f) if i < 5 else 0.
            inferior = acumulada_m
            acumulada_e += pe
            acumulada_m += p
            cdf_filas.append(dict(variable=variable, tiempo=str(i+1) if i<5 else '6+',
                                 frecuencia=f[i] if i<5 else 0, prob_empirica=pe,
                                 cdf_empirica=acumulada_e, modelo=nombre,
                                 prob_modelo=p, cdf_modelo=acumulada_m, limite_inferior=inferior))
    guardar_csv(salida/'distribuciones.csv', cdf_filas)
    (salida/'resumen.json').write_text(json.dumps(resumen, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    primera = [r for r in trazas if r['etapa']=='piloto' and r['replica']==1]
    consola = ["ESCENARIO 6 - OFICINA DE PAGOS", f"Modelos: {modelos}",
               "100 clientes; FIFO; un servidor; minutos; estado inicial vacío.",
               "\nPRIMEROS CINCO UNIFORMES UTILIZADOS (se intercalan llegada y servicio)"]
    usados = [(c[k], c['cliente'], k) for c in primera for k in ('u_llegada','u_servicio')]
    consola += [f"{i}: {u:.12f}, cliente {c}, {k}" for i,(u,c,k) in enumerate(usados[:5],1)]
    consola += ["\nTRES CLIENTES CONSECUTIVOS", "cliente  llegada  inicio  fin  espera"]
    consola += [f"{c['cliente']:7} {c['llegada']:8} {c['inicio']:7} {c['fin']:4} {c['espera']:7}" for c in primera[:3]]
    consola += ["\nCINCO REPLICAS INICIALES", "semilla     espera media   espera maxima"]
    consola += [f"{r['semilla']:10} {r['espera_media']:12.4f} {r['espera_maxima']:15}" for r in piloto]
    for nombre, est in [('PILOTO', estad_piloto), ('CONFIRMACION INDEPENDIENTE', estad_final)]:
        consola += [f"\n{nombre}: n={est['replicas']}; media={est['media']:.6f} min; "
                    f"IC95%=[{est['inferior']:.6f}, {est['superior']:.6f}]; "
                    f"error relativo={100*est['error_relativo']:.4f}%"]
    consola += [f"Plan con t del piloto: {n} réplicas NUEVAS; total ejecutado: {5+n}.",
                f"Estimación con t actualizado: {plan['n_con_t_actualizado']} réplicas (no es garantía).",
                f"¿Cumple precisión {100*precision:g}%?: {'SI' if resumen['cumple'] else 'NO'}",
                "El IC es aproximado y condicionado a los modelos de entrada; no mide su incertidumbre.",
                f"Resultados: {salida.resolve()}"]
    texto = '\n'.join(consola)+'\n'
    (salida/'demostracion.txt').write_text(texto, encoding='utf-8')
    print(texto)
    return resumen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--salida', type=Path, default=Path('resultados'))
    parser.add_argument('--semilla', type=int, default=20261103)
    parser.add_argument('--precision', type=float, default=.10)
    parser.add_argument('--empirica', action='store_true', help='Sensibilidad: usar ambas distribuciones empíricas')
    args = parser.parse_args()
    try:
        ejecutar(args.salida, args.semilla, args.precision,
                 {v:'empirica' for v in FRECUENCIAS} if args.empirica else None)
    except (ValueError, ArithmeticError) as error:
        parser.exit(2, f'Error: {error}\n')


if __name__ == '__main__':
    main()
