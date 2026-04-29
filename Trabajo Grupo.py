# UNIVERSIDAD NACIONAL ABIERTA Y A DISTANCIA - UNAD
# Curso: Programacion
# Ejercicio 1 - Sistema Integral de Gestion de Clientes,
# Servicios y Reservas para Software FJ
# Desarrollo segun requerimientos del PDF
#-------------------------------------------------------
import logging
from abc import ABC, abstractmethod

# CONFIGURACION DEL ARCHIVO DE LOGS

logging.basicConfig(
    filename='software_fj_logs.txt',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --------------------------------------------------------------
# EXCEPCIONES PERSONALIZADAS
# --------------------------------------------------------------
class ErrorSistema(Exception):
    pass

class ErrorValidacion(ErrorSistema):
    pass

class ErrorReserva(ErrorSistema):
    pass

class ErrorServicio(ErrorSistema):
    pass

# --------------------------------------------------------------
# CLASE ABSTRACTA GENERAL DEL SISTEMA
# representa cualquier entidad de servicio (cliente, servicio)
# --------------------------------------------------------------
class Entidad(ABC):
    def __init__(self, codigo):
        self._codigo = codigo

    @property
    def codigo(self):
        return self._codigo

#