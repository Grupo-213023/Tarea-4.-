"""Software FJ - sistema de gestion de clientes, servicios y reservas."""
import tkinter as tk
from tkinter import ttk, messagebox
from abc import ABC, abstractmethod
from datetime import datetime
import sys, os, re

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs.txt")
ALFANUM = re.compile(r'^[A-Za-z0-9 \-]+$')   # letras + numeros + espacio + guion
ALFA    = re.compile(r'^[A-Za-z ]+$')         # solo letras y espacios
MONEDA  = "COP"

def log(nivel, msg):
    """Guarda eventos/errores en logs.txt."""
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [{nivel}] {msg}\n")
    except OSError:
        pass

def fmt(v):                                    # Formatea como pesos colombianos.
    return f"{MONEDA} ${v:,.0f}"


class SoftwareFJError(Exception): pass         # Excepcion base del sistema.


# ---------- Clase abstracta base ----------
class Entidad(ABC):
    _cont = 0
    def __init__(self):
        Entidad._cont += 1
        self._id = Entidad._cont
        self._fecha = datetime.now()
    @property
    def id(self): return self._id
    @abstractmethod
    def describir(self): ...
    def __str__(self): return self.describir()


# ---------- Cliente ----------
class Cliente(Entidad):
    def __init__(self, nombre, documento, correo="", telefono=""):
        super().__init__()
        self.nombre, self.documento = nombre, documento
        self.correo, self.telefono  = correo, telefono

    @property
    def nombre(self): return self._nombre
    @nombre.setter
    def nombre(self, v):
        if not isinstance(v, str) or len(v.strip()) < 3:
            raise SoftwareFJError("Nombre invalido (minimo 3 caracteres).")
        self._nombre = v.strip()

    @property
    def documento(self): return self._documento
    @documento.setter
    def documento(self, v):
        v = (v or "").strip()
        if not v.isdigit() or not (5 <= len(v) <= 15):
            raise SoftwareFJError("Documento invalido (5-15 digitos).")
        self._documento = v

    @property
    def correo(self): return self._correo
    @correo.setter
    def correo(self, v):
        v = (v or "").strip()
        if v and ("@" not in v or "." not in v):
            raise SoftwareFJError("Correo invalido.")
        self._correo = v

    @property
    def telefono(self): return self._telefono
    @telefono.setter
    def telefono(self, v):
        v = (v or "").strip()
        if v and not v.isdigit():
            raise SoftwareFJError("Telefono invalido (solo numeros).")
        self._telefono = v

    def describir(self):
        return f"Cliente #{self.id} - {self.nombre} (Doc: {self.documento})"


# ---------- Servicio abstracto + 3 subclases ----------
class Servicio(Entidad):
    def __init__(self, nombre, precio):
        super().__init__()
        if not nombre or not str(nombre).strip():
            raise SoftwareFJError("Nombre del servicio obligatorio.")
        try: precio = float(precio)
        except (TypeError, ValueError):
            raise SoftwareFJError(f"Precio ({MONEDA}) debe ser numerico.")
        if precio <= 0:
            raise SoftwareFJError(f"Precio ({MONEDA}) debe ser mayor a cero.")
        self._nombre, self._precio = nombre.strip(), precio

    @property
    def nombre(self): return self._nombre
    @property
    def precio(self): return self._precio

    @abstractmethod
    def tipo(self): ...
    # Sobrecarga simulada: cantidad, descuento e IVA opcionales.
    @abstractmethod
    def calcular_costo(self, cantidad=1, descuento=0.0, iva=0.0): ...

    def _validar(self, cantidad, descuento, iva=0.0):
        if cantidad <= 0:
            raise SoftwareFJError("La cantidad debe ser mayor a cero.")
        if not (0.0 <= descuento <= 1.0):
            raise SoftwareFJError("Descuento debe estar entre 0 y 1.")
        if not (0.0 <= iva <= 1.0):
            raise SoftwareFJError("IVA debe estar entre 0 y 1.")

    def describir(self):
        return f"[{self.tipo()}] #{self.id} {self.nombre} - {fmt(self.precio)}"


class ReservaSala(Servicio):
    def __init__(self, nombre, precio, capacidad):
        super().__init__(nombre, precio)
        v = (str(capacidad) if capacidad is not None else "").strip()
        if not v or not ALFANUM.match(v):
            raise SoftwareFJError("Capacidad debe ser alfanumerica (ej. '30 personas', 'Sala 12A').")
        self.capacidad = v
    def tipo(self): return "Reserva de Sala"
    def calcular_costo(self, cantidad=1, descuento=0.0, iva=0.0):
        self._validar(cantidad, descuento, iva)
        return self.precio * cantidad * (1 - descuento) * (1 + iva)


class AlquilerEquipo(Servicio):
    def __init__(self, nombre, precio, marca="Generica"):
        super().__init__(nombre, precio)
        v = (marca or "Generica").strip() or "Generica"
        if not ALFA.match(v):
            raise SoftwareFJError("Marca debe contener solo letras.")
        self.marca = v
    def tipo(self): return "Alquiler de Equipo"
    def calcular_costo(self, cantidad=1, descuento=0.0, iva=0.0):
        self._validar(cantidad, descuento, iva)
        bono = 0.1 if cantidad >= 7 else 0     # 10% extra a partir de 7 dias.
        return self.precio * cantidad * (1 - descuento - bono) * (1 + iva)


class Asesoria(Servicio):
    def __init__(self, nombre, precio, especialidad):
        super().__init__(nombre, precio)
        v = (especialidad or "").strip()
        if not v or not ALFA.match(v):
            raise SoftwareFJError("Especialidad debe contener solo letras.")
        self.especialidad = v
    def tipo(self): return "Asesoria"
    def calcular_costo(self, cantidad=1, descuento=0.0, iva=0.0):
        self._validar(cantidad, descuento, iva)
        return self.precio * cantidad * (1 - descuento) * (1 + iva)


# ---------- Reserva con maquina de estados ----------
ESTADOS_TRANS = {
    "confirmar": ({"PENDIENTE"},               "CONFIRMADA"),
    "cancelar":  ({"PENDIENTE", "CONFIRMADA"}, "CANCELADA"),
    "procesar":  ({"CONFIRMADA"},              "PROCESADA"),
}

class Reserva(Entidad):
    def __init__(self, cliente, servicio, cantidad=1, descuento=0.0, iva=0.0):
        if not isinstance(cliente, Cliente) or not isinstance(servicio, Servicio):
            raise SoftwareFJError("Cliente o servicio invalido.")
        super().__init__()
        self.cliente, self.servicio          = cliente, servicio
        self.cantidad, self.descuento, self.iva = cantidad, descuento, iva
        self.estado = "PENDIENTE"
        try:
            self.costo = servicio.calcular_costo(cantidad, descuento, iva)
        except Exception as e:
            raise SoftwareFJError(f"No se pudo calcular el costo: {e}") from e

    def _cambiar(self, accion):
        validos, nuevo = ESTADOS_TRANS[accion]
        if self.estado not in validos:
            raise SoftwareFJError(
                f"No se puede {accion}: estado actual '{self.estado}', requerido {sorted(validos)}.")
        self.estado = nuevo
        log("EVENTO", f"Reserva #{self.id} -> {nuevo}")

    def confirmar(self): self._cambiar("confirmar")
    def cancelar(self):  self._cambiar("cancelar")
    def procesar(self):  self._cambiar("procesar")

    def describir(self):
        return (f"Reserva #{self.id} [{self.estado}] | {self.cliente.nombre} -> "
                f"{self.servicio.nombre} | x{self.cantidad} | {fmt(self.costo)} "
                f"| {self._fecha:%Y-%m-%d %H:%M}")


# ---------- Gestor central ----------
TIPOS = {"sala": ReservaSala, "equipo": AlquilerEquipo, "asesoria": Asesoria}
LABEL_EXTRA = {"sala":     "Capacidad (alfanumerica) *",
               "equipo":   "Marca (solo letras)",
               "asesoria": "Especialidad (solo letras) *"}

class Gestor:
    def __init__(self):
        self.clientes, self.servicios, self.reservas = [], [], []

    def registrar_cliente(self, nombre, doc, correo="", telefono=""):
        if any(c.documento == (doc or "").strip() for c in self.clientes):
            raise SoftwareFJError(f"Ya existe cliente con documento {doc}.")
        c = Cliente(nombre, doc, correo, telefono)
        self.clientes.append(c); log("EVENTO", f"Cliente: {c}")
        return c

    def crear_servicio(self, tipo, nombre, precio, extra=None):
        cls = TIPOS.get((tipo or "").strip().lower())
        if not cls:
            raise SoftwareFJError(f"Tipo desconocido: '{tipo}' (use sala/equipo/asesoria).")
        if cls is AlquilerEquipo and not extra: extra = "Generica"
        s = cls(nombre, precio, extra)
        self.servicios.append(s); log("EVENTO", f"Servicio: {s}")
        return s

    def _buscar(self, lista, id_, tipo):
        for x in lista:
            if x.id == id_: return x
        raise SoftwareFJError(f"No existe {tipo} con id {id_}.")

    def crear_reserva(self, id_cli, id_serv, cantidad=1, descuento=0.0, iva=0.0):
        r = Reserva(self._buscar(self.clientes, id_cli, "cliente"),
                    self._buscar(self.servicios, id_serv, "servicio"),
                    cantidad, descuento, iva)
        self.reservas.append(r); log("EVENTO", f"Reserva: {r}")
        return r

    def buscar_reserva(self, id_):
        return self._buscar(self.reservas, id_, "reserva")


# ---------- Interfaz Tkinter ----------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Software FJ"); self.geometry("950x620")
        self.g = Gestor(); log("INFO", "GUI iniciada")
        try: ttk.Style(self).theme_use("clam")
        except tk.TclError: pass

        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=10, pady=10)
        self.tab_cli = ttk.Frame(nb, padding=10); nb.add(self.tab_cli, text="Clientes")
        self.tab_srv = ttk.Frame(nb, padding=10); nb.add(self.tab_srv, text="Servicios")
        self.tab_res = ttk.Frame(nb, padding=10); nb.add(self.tab_res, text="Reservas")
        self._build_cli(); self._build_srv(); self._build_res()

    def _tabla(self, parent, columnas, anchos):
        t = ttk.Treeview(parent, columns=columnas, show="headings", height=9)
        for c, a in zip(columnas, anchos):
            t.heading(c, text=c.capitalize()); t.column(c, width=a, anchor="w")
        t.pack(fill="both", expand=True, pady=(8, 0)); return t

    def _accion(self, fn, ok_msg, refresh):
        try: r = fn()
        except SoftwareFJError as e:
            log("ERROR", f"GUI: {e}"); messagebox.showerror("Error", str(e))
        except Exception as e:
            log("ERROR", f"GUI INESP: {e}"); messagebox.showerror("Error inesperado", str(e))
        else:
            messagebox.showinfo("Exito", f"{ok_msg}\n{r}"); refresh()
        finally:
            log("INFO", "Operacion GUI finalizada")

    # --- Clientes ---
    def _build_cli(self):
        f = ttk.LabelFrame(self.tab_cli, text="Nuevo cliente", padding=10); f.pack(fill="x")
        self.vc = {k: tk.StringVar() for k in ("n","d","c","t")}
        for i, (k, lbl) in enumerate([("n","Nombre *"),("d","Documento *"),
                                       ("c","Correo"),("t","Telefono")]):
            ttk.Label(f, text=lbl).grid(row=i, column=0, sticky="w", padx=4, pady=3)
            ttk.Entry(f, textvariable=self.vc[k], width=35).grid(row=i, column=1, padx=4, pady=3)
        ttk.Button(f, text="Registrar", command=self._add_cli).grid(row=4, column=1, sticky="w", pady=6)
        self.tc = self._tabla(self.tab_cli, ("id","nombre","documento","correo","telefono"),
                               [50, 200, 130, 200, 130])

    def _add_cli(self):
        self._accion(
            lambda: self.g.registrar_cliente(self.vc["n"].get(), self.vc["d"].get(),
                                              self.vc["c"].get(), self.vc["t"].get()),
            "Cliente registrado:", lambda: (self._refresh_cli(), self._refresh_combos(),
                                              [v.set("") for v in self.vc.values()]))

    def _refresh_cli(self):
        self.tc.delete(*self.tc.get_children())
        for c in self.g.clientes:
            self.tc.insert("", "end", values=(c.id, c.nombre, c.documento, c.correo, c.telefono))

    # --- Servicios ---
    def _build_srv(self):
        f = ttk.LabelFrame(self.tab_srv, text="Nuevo servicio", padding=10); f.pack(fill="x")
        self.vs = {"tipo": tk.StringVar(value="sala"), "n": tk.StringVar(),
                   "p": tk.StringVar(), "x": tk.StringVar()}
        ttk.Label(f, text="Tipo *").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        cb = ttk.Combobox(f, textvariable=self.vs["tipo"], values=list(TIPOS),
                          state="readonly", width=20)
        cb.grid(row=0, column=1, sticky="w", padx=4, pady=3)
        cb.bind("<<ComboboxSelected>>", lambda _e: self._on_tipo_change())

        ttk.Label(f, text="Nombre *").grid(row=1, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(f, textvariable=self.vs["n"], width=35).grid(row=1, column=1, padx=4, pady=3)
        ttk.Label(f, text=f"Precio ({MONEDA}) *").grid(row=2, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(f, textvariable=self.vs["p"], width=35).grid(row=2, column=1, padx=4, pady=3)

        # Etiqueta dinamica segun el tipo elegido (capacidad/marca/especialidad).
        self.lbl_extra = ttk.Label(f, text=LABEL_EXTRA["sala"])
        self.lbl_extra.grid(row=3, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(f, textvariable=self.vs["x"], width=35).grid(row=3, column=1, padx=4, pady=3)

        ttk.Button(f, text="Crear", command=self._add_srv).grid(row=4, column=1, sticky="w", pady=6)
        self.ts = self._tabla(self.tab_srv, ("id","tipo","nombre","precio","extra"),
                               [50, 150, 220, 150, 200])

    def _on_tipo_change(self):
        self.lbl_extra.config(text=LABEL_EXTRA[self.vs["tipo"].get()])
        self.vs["x"].set("")

    def _add_srv(self):
        def hacer():
            try: precio = float(self.vs["p"].get())
            except ValueError: raise SoftwareFJError(f"Precio ({MONEDA}) debe ser numero.")
            extra = self.vs["x"].get() or None
            return self.g.crear_servicio(self.vs["tipo"].get(), self.vs["n"].get(), precio, extra)
        self._accion(hacer, "Servicio creado:",
                     lambda: (self._refresh_srv(), self._refresh_combos(),
                              [self.vs[k].set("") for k in ("n","p","x")]))

    def _refresh_srv(self):
        self.ts.delete(*self.ts.get_children())
        for s in self.g.servicios:
            extra = getattr(s, "capacidad", None) or getattr(s, "marca", None) or getattr(s, "especialidad", "")
            self.ts.insert("", "end", values=(s.id, s.tipo(), s.nombre, fmt(s.precio), extra))

    # --- Reservas ---
    def _build_res(self):
        f = ttk.LabelFrame(self.tab_res, text="Nueva reserva", padding=10); f.pack(fill="x")
        self.vr = {k: tk.StringVar(value=d) for k, d in
                   [("c",""),("s",""),("q","1"),("d","0"),("i","0")]}
        ttk.Label(f, text="Cliente *").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        self.cb_c = ttk.Combobox(f, textvariable=self.vr["c"], width=42, state="readonly")
        self.cb_c.grid(row=0, column=1, padx=4, sticky="w")
        ttk.Label(f, text="Servicio *").grid(row=1, column=0, sticky="w", padx=4, pady=3)
        self.cb_s = ttk.Combobox(f, textvariable=self.vr["s"], width=42, state="readonly")
        self.cb_s.grid(row=1, column=1, padx=4, sticky="w")
        for i, (k, lbl) in enumerate([("q","Cantidad *"),("d","Descuento (0-1)"),("i","IVA (0-1)")], 2):
            ttk.Label(f, text=lbl).grid(row=i, column=0, sticky="w", padx=4, pady=3)
            ttk.Entry(f, textvariable=self.vr[k], width=10).grid(row=i, column=1, sticky="w", padx=4)
        ttk.Button(f, text="Reservar", command=self._add_res).grid(row=5, column=1, sticky="w", pady=6)

        # Botones para cambiar el estado de la reserva seleccionada en la tabla.
        bf = ttk.Frame(self.tab_res); bf.pack(fill="x", pady=(8,0))
        ttk.Label(bf, text="Acciones (selecciona una reserva):").pack(side="left", padx=4)
        for txt, fn in [("Confirmar","confirmar"),("Cancelar","cancelar"),("Procesar","procesar")]:
            ttk.Button(bf, text=txt, command=lambda a=fn: self._accion_estado(a)).pack(side="left", padx=4)

        self.tr = self._tabla(self.tab_res,
                               ("id","cliente","servicio","cant","costo","estado","fecha"),
                               [50, 160, 200, 60, 140, 110, 130])

    def _refresh_combos(self):
        self.cb_c["values"] = [f"{c.id} - {c.nombre}" for c in self.g.clientes]
        self.cb_s["values"] = [f"{s.id} - {s.tipo()}: {s.nombre}" for s in self.g.servicios]

    def _add_res(self):
        def hacer():
            if not self.vr["c"].get() or not self.vr["s"].get():
                raise SoftwareFJError("Seleccione cliente y servicio.")
            try:
                cid = int(self.vr["c"].get().split(" - ")[0])
                sid = int(self.vr["s"].get().split(" - ")[0])
                q   = int(self.vr["q"].get())
                d   = float(self.vr["d"].get() or "0")
                i   = float(self.vr["i"].get() or "0")
            except ValueError: raise SoftwareFJError("Cantidad/descuento/IVA numericos.")
            return self.g.crear_reserva(cid, sid, q, d, i)
        self._accion(hacer, "Reserva creada:", self._refresh_res)

    def _accion_estado(self, accion):
        sel = self.tr.selection()
        if not sel:
            messagebox.showwarning("Atencion", "Selecciona una reserva."); return
        rid = int(self.tr.item(sel[0])["values"][0])
        def hacer():
            r = self.g.buscar_reserva(rid); getattr(r, accion)(); return r
        self._accion(hacer, f"Reserva {accion}:", self._refresh_res)

    def _refresh_res(self):
        self.tr.delete(*self.tr.get_children())
        for r in self.g.reservas:
            self.tr.insert("", "end", values=(r.id, r.cliente.nombre,
                f"{r.servicio.tipo()}: {r.servicio.nombre}", r.cantidad,
                fmt(r.costo), r.estado, r._fecha.strftime("%Y-%m-%d %H:%M")))


# ---------- Simulacion ----------
def simular():
    g = Gestor(); log("INFO", "Inicio simulacion")
    print("=" * 50, "\nSIMULACION SOFTWARE FJ\n", "=" * 50, sep="")
    ctx = {}
    def correr(n, desc, accion):
        print(f"\n[{n:02d}] {desc}")
        try: r = accion()
        except SoftwareFJError as e:
            print(f"   -> Error: {e}"); log("ERROR", f"OP{n}: {e}")
        except Exception as e:
            print(f"   -> Inesperado: {e}"); log("ERROR", f"OP{n} INESP: {e}")
        else:
            print(f"   -> OK: {r}"); return r
        finally:
            log("INFO", f"OP{n} fin: {desc}")

    ctx["c1"] = correr(1, "Cliente valido",
        lambda: g.registrar_cliente("Juan Perez", "1023456789", "j@x.com"))
    correr(2, "Nombre invalido", lambda: g.registrar_cliente("J", "1023456790"))
    correr(3, "Documento invalido", lambda: g.registrar_cliente("Ana Gomez", "ABC"))
    ctx["c2"] = correr(4, "Cliente valido 2",
        lambda: g.registrar_cliente("Maria Lopez", "1098765432"))
    ctx["s1"] = correr(5, "Sala valida (capacidad alfanumerica)",
        lambda: g.crear_servicio("sala", "Sala Premium", 50000, "30 personas"))
    ctx["s2"] = correr(6, "Equipo valido (marca alfabetica)",
        lambda: g.crear_servicio("equipo", "Proyector", 30000, "Epson"))
    ctx["s3"] = correr(7, "Asesoria valida (especialidad alfabetica)",
        lambda: g.crear_servicio("asesoria", "Consultoria TI", 120000, "Ciberseguridad"))
    correr(8, "Marca con numeros (debe fallar)",
        lambda: g.crear_servicio("equipo", "Camara", 20000, "Sony123"))
    correr(9, "Precio negativo (debe fallar)",
        lambda: g.crear_servicio("sala", "Mini", -500, "10A"))

    r1 = correr(10, "Reserva valida sala 3h con IVA 19%",
        lambda: g.crear_reserva(ctx["c1"].id, ctx["s1"].id, cantidad=3, iva=0.19))
    r2 = correr(11, "Reserva valida equipo 7d con bono",
        lambda: g.crear_reserva(ctx["c2"].id, ctx["s2"].id, cantidad=7))
    r3 = correr(12, "Reserva valida asesoria 2 sesiones 10% desc",
        lambda: g.crear_reserva(ctx["c1"].id, ctx["s3"].id, cantidad=2, descuento=0.10))
    correr(13, "Cliente inexistente",
        lambda: g.crear_reserva(999, ctx["s1"].id))
    correr(14, "Cantidad cero",
        lambda: g.crear_reserva(ctx["c1"].id, ctx["s1"].id, cantidad=0))
    correr(15, "Confirmar reserva 1", lambda: (r1.confirmar(), r1)[1])
    correr(16, "Procesar reserva 1", lambda: (r1.procesar(), r1)[1])
    correr(17, "Cancelar reserva 2", lambda: (r2.cancelar(), r2)[1])
    correr(18, "Procesar reserva sin confirmar (debe fallar)",
        lambda: (r3.procesar(), r3)[1])

    print(f"\nResumen: {len(g.clientes)} clientes, {len(g.servicios)} servicios, {len(g.reservas)} reservas")
    for r in g.reservas: print(" -", r)
    log("INFO", "Fin simulacion")


if __name__ == "__main__":
    if "--sim" in sys.argv:
        simular()
    else:
        try: App().mainloop()
        finally: log("INFO", "App cerrada")
