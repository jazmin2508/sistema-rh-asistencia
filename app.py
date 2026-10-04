import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import re
from datetime import datetime, date, time
from io import BytesIO
import plotly.express as px

DB = "rh.db"

st.set_page_config(page_title="Sistema RH | Asistencia", page_icon="🕐", layout="wide")

def conn():
    c = sqlite3.connect(DB, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        rol TEXT NOT NULL DEFAULT 'RH',
        activo INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS trabajadores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        curp TEXT UNIQUE NOT NULL,
        nombre TEXT NOT NULL,
        apellido_paterno TEXT NOT NULL,
        apellido_materno TEXT DEFAULT '',
        fecha_nacimiento TEXT,
        area TEXT NOT NULL,
        puesto TEXT NOT NULL,
        numero_empleado TEXT UNIQUE,
        fecha_ingreso TEXT,
        activo INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS asistencias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trabajador_id INTEGER NOT NULL,
        fecha TEXT NOT NULL,
        hora_entrada TEXT,
        hora_salida TEXT,
        estado TEXT DEFAULT 'Presente',
        observacion TEXT DEFAULT '',
        registrado_por TEXT,
        creado_en TEXT NOT NULL,
        FOREIGN KEY(trabajador_id) REFERENCES trabajadores(id)
    );
    CREATE TABLE IF NOT EXISTS incidencias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trabajador_id INTEGER NOT NULL,
        fecha TEXT NOT NULL,
        tipo TEXT NOT NULL,
        descripcion TEXT NOT NULL,
        observacion_rh TEXT DEFAULT '',
        registrado_por TEXT,
        creado_en TEXT NOT NULL,
        FOREIGN KEY(trabajador_id) REFERENCES trabajadores(id)
    );
    """)
    cur = c.execute("SELECT COUNT(*) n FROM usuarios")
    if cur.fetchone()["n"] == 0:
        c.execute("INSERT INTO usuarios(usuario,password,rol) VALUES(?,?,?)",
                  ("admin", sha("admin123"), "Administrador"))
    c.commit()
    c.close()

def sha(s): return hashlib.sha256(s.encode()).hexdigest()

def q(sql, params=(), one=False):
    c = conn()
    cur = c.execute(sql, params)
    rows = cur.fetchall()
    c.close()
    return rows[0] if one and rows else (None if one else rows)

def exec_sql(sql, params=()):
    c = conn()
    cur = c.execute(sql, params)
    c.commit()
    rid = cur.lastrowid
    c.close()
    return rid

def valid_curp(curp):
    return bool(re.fullmatch(r"[A-ZÑ]{4}\d{6}[HM][A-ZÑ]{5}[A-Z0-9]\d", curp.upper()))

def excel_bytes(df):
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Datos")
    return out.getvalue()

def login():
    st.title("🕐 Sistema RH — Control de Asistencia")
    st.caption("Acceso para Recursos Humanos")
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        ok = st.form_submit_button("Iniciar sesión", type="primary")
    if ok:
        user = q("SELECT * FROM usuarios WHERE usuario=? AND activo=1", (u,), True)
        if user and user["password"] == sha(p):
            st.session_state.user = dict(user)
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")

def dashboard():
    st.title("📊 Panel de control")
    hoy = date.today().isoformat()
    total = q("SELECT COUNT(*) n FROM trabajadores WHERE activo=1", one=True)["n"]
    ent = q("SELECT COUNT(*) n FROM asistencias WHERE fecha=? AND hora_entrada IS NOT NULL", (hoy,), True)["n"]
    sal = q("SELECT COUNT(*) n FROM asistencias WHERE fecha=? AND hora_salida IS NOT NULL", (hoy,), True)["n"]
    inc = q("SELECT COUNT(*) n FROM incidencias WHERE fecha=?", (hoy,), True)["n"]
    a,b,c,d = st.columns(4)
    a.metric("👥 Trabajadores activos", total)
    b.metric("🟢 Entradas hoy", ent)
    c.metric("🔵 Salidas hoy", sal)
    d.metric("⚠️ Incidencias hoy", inc)

    rows = q("""SELECT t.area, COUNT(DISTINCT a.trabajador_id) presentes
                FROM asistencias a JOIN trabajadores t ON t.id=a.trabajador_id
                WHERE a.fecha=? AND a.hora_entrada IS NOT NULL
                GROUP BY t.area ORDER BY presentes DESC""", (hoy,))
    if rows:
        df = pd.DataFrame([dict(x) for x in rows])
        st.subheader("Asistencia por área — hoy")
        st.plotly_chart(px.bar(df, x="area", y="presentes", text_auto=True), use_container_width=True)

def registro_asistencia():
    st.title("🕐 Registrar asistencia")
    st.write("El trabajador puede identificarse mediante su CURP.")
    curp = st.text_input("CURP", max_chars=18).strip().upper()
    if st.button("Buscar trabajador", type="primary"):
        if not valid_curp(curp):
            st.error("La CURP no tiene un formato válido.")
            return
        t = q("SELECT * FROM trabajadores WHERE curp=? AND activo=1", (curp,), True)
        if not t:
            st.error("No se encontró un trabajador activo con esa CURP.")
            return
        st.session_state.trabajador_reg = dict(t)

    t = st.session_state.get("trabajador_reg")
    if not t: return

    st.success(f"Trabajador identificado: {t['nombre']} {t['apellido_paterno']} {t['apellido_materno']}")
    x,y,z = st.columns(3)
    x.info(f"**Área:** {t['area']}")
    y.info(f"**Puesto:** {t['puesto']}")
    z.info(f"**Empleado:** {t['numero_empleado'] or 'Sin número'}")

    hoy = date.today().isoformat()
    a = q("SELECT * FROM asistencias WHERE trabajador_id=? AND fecha=?", (t["id"], hoy), True)
    obs = st.text_area("Observación (opcional)", key="obs_reg")
    c1,c2 = st.columns(2)
    with c1:
        if st.button("🟢 Registrar entrada", use_container_width=True, disabled=bool(a and a["hora_entrada"])):
            if a:
                st.error("Ya existe una entrada registrada para hoy.")
            else:
                exec_sql("""INSERT INTO asistencias
                    (trabajador_id,fecha,hora_entrada,estado,observacion,registrado_por,creado_en)
                    VALUES(?,?,?,?,?,?,?)""",
                    (t["id"],hoy,datetime.now().strftime("%H:%M:%S"),"Presente",obs,st.session_state.user["usuario"],datetime.now().isoformat()))
                st.success("Entrada registrada correctamente.")
                st.rerun()
    with c2:
        if st.button("🔵 Registrar salida", use_container_width=True, disabled=not bool(a and a["hora_entrada"]) or bool(a and a["hora_salida"])):
            exec_sql("UPDATE asistencias SET hora_salida=?, observacion=? WHERE id=?",
                     (datetime.now().strftime("%H:%M:%S"), obs, a["id"]))
            st.success("Salida registrada correctamente.")
            st.rerun()

def trabajadores():
    st.title("👥 Trabajadores")
    tab1,tab2,tab3 = st.tabs(["Consultar","Agregar","Editar estado"])
    with tab1:
        rows=q("""SELECT id,curp,numero_empleado,nombre,apellido_paterno,apellido_materno,
                  area,puesto,fecha_ingreso,activo FROM trabajadores ORDER BY apellido_paterno""")
        df=pd.DataFrame([dict(x) for x in rows])
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button("📥 Exportar trabajadores a Excel", excel_bytes(df), "trabajadores.xlsx")
        else: st.info("No hay trabajadores registrados.")
    with tab2:
        with st.form("nuevo"):
            curp=st.text_input("CURP").strip().upper()
            nom=st.text_input("Nombre")
            ap=st.text_input("Apellido paterno")
            am=st.text_input("Apellido materno")
            fn=st.date_input("Fecha de nacimiento", value=date(2000,1,1))
            area=st.text_input("Área")
            puesto=st.text_input("Puesto")
            ne=st.text_input("Número de empleado")
            fi=st.date_input("Fecha de ingreso", value=date.today())
            save=st.form_submit_button("Guardar trabajador", type="primary")
        if save:
            errores=[]
            if not valid_curp(curp): errores.append("CURP inválida.")
            if not nom or not ap: errores.append("Nombre y apellido paterno son obligatorios.")
            if not area: errores.append("Área obligatoria.")
            if not puesto: errores.append("Puesto obligatorio.")
            if q("SELECT id FROM trabajadores WHERE curp=?", (curp,), True): errores.append("La CURP ya existe.")
            if ne and q("SELECT id FROM trabajadores WHERE numero_empleado=?", (ne,), True): errores.append("El número de empleado ya existe.")
            if errores:
                for e in errores: st.error(e)
            else:
                exec_sql("""INSERT INTO trabajadores
                (curp,nombre,apellido_paterno,apellido_materno,fecha_nacimiento,area,puesto,numero_empleado,fecha_ingreso)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (curp,nom,ap,am,str(fn),area,puesto,ne,str(fi)))
                st.success("Trabajador registrado.")
    with tab3:
        rows=q("SELECT id,curp,nombre,apellido_paterno,area,puesto,activo FROM trabajadores ORDER BY nombre")
        if rows:
            options={f"{r['curp']} — {r['nombre']} {r['apellido_paterno']}":r["id"] for r in rows}
            sel=st.selectbox("Trabajador", list(options))
            r=next(x for x in rows if x["id"]==options[sel])
            new=st.toggle("Trabajador activo", value=bool(r["activo"]))
            if st.button("Guardar estado"):
                exec_sql("UPDATE trabajadores SET activo=? WHERE id=?", (int(new),r["id"]))
                st.success("Estado actualizado.")
                st.rerun()

def historial():
    st.title("📋 Historial de asistencia")
    c1,c2=st.columns(2)
    ini=c1.date_input("Desde", value=date.today().replace(day=1))
    fin=c2.date_input("Hasta", value=date.today())
    rows=q("""SELECT a.fecha,a.hora_entrada,a.hora_salida,a.estado,
              t.curp,t.nombre,t.apellido_paterno,t.apellido_materno,t.area,t.puesto,
              a.observacion,a.registrado_por
              FROM asistencias a JOIN trabajadores t ON t.id=a.trabajador_id
              WHERE a.fecha BETWEEN ? AND ? ORDER BY a.fecha DESC,a.hora_entrada DESC""",
            (str(ini),str(fin)))
    df=pd.DataFrame([dict(x) for x in rows])
    if df.empty: st.info("No hay registros en el periodo.")
    else:
        st.dataframe(df,use_container_width=True,hide_index=True)
        st.download_button("📥 Exportar a Excel",excel_bytes(df),"historial_asistencia.xlsx")

def incidencias():
    st.title("⚠️ Incidencias y observaciones de RH")
    rows=q("""SELECT i.id,i.fecha,t.curp,t.nombre,t.apellido_paterno,t.area,t.puesto,
              i.tipo,i.descripcion,i.observacion_rh,i.registrado_por
              FROM incidencias i JOIN trabajadores t ON t.id=i.trabajador_id
              ORDER BY i.fecha DESC,i.id DESC""")
    df=pd.DataFrame([dict(x) for x in rows])
    if not df.empty:
        st.dataframe(df,use_container_width=True,hide_index=True)
        st.download_button("📥 Exportar incidencias",excel_bytes(df),"incidencias.xlsx")
    st.subheader("Registrar incidencia")
    trs=q("SELECT * FROM trabajadores WHERE activo=1 ORDER BY nombre")
    if not trs: st.warning("Primero registra trabajadores."); return
    opts={f"{r['curp']} — {r['nombre']} {r['apellido_paterno']}":r["id"] for r in trs}
    with st.form("inc"):
        sel=st.selectbox("Trabajador",list(opts))
        tipo=st.selectbox("Tipo",["Retardo","Falta","Permiso","Dato incompleto","Error de registro","Otra"])
        fecha=st.date_input("Fecha",date.today())
        desc=st.text_area("Descripción")
        obs=st.text_area("Observación de RH")
        save=st.form_submit_button("Guardar incidencia",type="primary")
    if save:
        if not desc.strip(): st.error("La descripción es obligatoria.")
        else:
            exec_sql("""INSERT INTO incidencias
            (trabajador_id,fecha,tipo,descripcion,observacion_rh,registrado_por,creado_en)
            VALUES(?,?,?,?,?,?,?)""",
            (opts[sel],str(fecha),tipo,desc,obs,st.session_state.user["usuario"],datetime.now().isoformat()))
            st.success("Incidencia registrada.")
            st.rerun()

def reportes():
    st.title("📑 Informes y exportaciones")
    ini=st.date_input("Desde",date.today().replace(day=1),key="ri")
    fin=st.date_input("Hasta",date.today(),key="rf")
    rows=q("""SELECT t.curp,t.nombre,t.apellido_paterno,t.apellido_materno,t.area,t.puesto,
              a.fecha,a.hora_entrada,a.hora_salida,a.estado,a.observacion
              FROM asistencias a JOIN trabajadores t ON t.id=a.trabajador_id
              WHERE a.fecha BETWEEN ? AND ? ORDER BY a.fecha,t.apellido_paterno""",(str(ini),str(fin)))
    df=pd.DataFrame([dict(x) for x in rows])
    if df.empty:
        st.info("No hay datos para el periodo.")
    else:
        st.dataframe(df,use_container_width=True,hide_index=True)
        st.download_button("📥 Descargar informe Excel",excel_bytes(df),"informe_rh.xlsx",type="primary")

def protocolo():
    st.title("💬 Protocolo breve de comunicación empática")
    steps=[
        ("1. Escuchar","Permitir que la persona explique su situación sin interrumpir."),
        ("2. Comprender","Confirmar lo entendido y evitar juicios o suposiciones."),
        ("3. Registrar","Anotar únicamente información objetiva y relevante."),
        ("4. Orientar","Explicar el procedimiento o las alternativas disponibles."),
        ("5. Dar seguimiento","Indicar qué sucederá después y cuándo corresponde revisar el caso.")
    ]
    for h,t in steps: st.info(f"**{h}**\n\n{t}")
    st.success("Objetivo: registrar incidencias de forma clara, respetuosa y consistente.")

def usuarios():
    st.title("⚙️ Usuarios de RH")
    rows=q("SELECT id,usuario,rol,activo FROM usuarios ORDER BY usuario")
    st.dataframe(pd.DataFrame([dict(x) for x in rows]),use_container_width=True,hide_index=True)
    st.subheader("Crear usuario")
    with st.form("user"):
        u=st.text_input("Usuario")
        p=st.text_input("Contraseña",type="password")
        rol=st.selectbox("Rol",["RH","Administrador","Consulta"])
        save=st.form_submit_button("Crear")
    if save:
        if not u or len(p)<6: st.error("Usuario obligatorio y contraseña de al menos 6 caracteres.")
        elif q("SELECT id FROM usuarios WHERE usuario=?",(u,),True): st.error("Ese usuario ya existe.")
        else:
            exec_sql("INSERT INTO usuarios(usuario,password,rol) VALUES(?,?,?)",(u,sha(p),rol))
            st.success("Usuario creado."); st.rerun()

def main():
    init_db()
    if "user" not in st.session_state:
        login(); return
    with st.sidebar:
        st.title("🏢 Sistema RH")
        st.caption(f"Usuario: {st.session_state.user['usuario']}")
        menu=st.radio("Menú",[
            "📊 Dashboard","🕐 Registrar asistencia","👥 Trabajadores",
            "📋 Historial","⚠️ Incidencias","📑 Informes","💬 Protocolo RH",
            "⚙️ Usuarios"
        ])
        if st.button("Cerrar sesión"):
            del st.session_state["user"]; st.rerun()
    if menu=="📊 Dashboard": dashboard()
    elif menu=="🕐 Registrar asistencia": registro_asistencia()
    elif menu=="👥 Trabajadores": trabajadores()
    elif menu=="📋 Historial": historial()
    elif menu=="⚠️ Incidencias": incidencias()
    elif menu=="📑 Informes": reportes()
    elif menu=="💬 Protocolo RH": protocolo()
    elif menu=="⚙️ Usuarios":
        if st.session_state.user["rol"]=="Administrador": usuarios()
        else: st.warning("Solo un Administrador puede gestionar usuarios.")

if __name__=="__main__":
    main()
