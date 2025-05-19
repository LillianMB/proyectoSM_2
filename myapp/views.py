from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from .forms import RegistroUsuarioForm
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
import json
from .models import Grupos, Equipos, Actividades, Preguntas, Respuestas, Usuario, Calendario, Calificaciones, Respuestas_Alumno, Notificacion
from django.utils.dateparse import parse_date
from django.db.models import Avg
from datetime import datetime
import random
from datetime import date
from django.db.models import Q

def registro(request):
    if request.method == "POST":
        form = RegistroUsuarioForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("alumno" if user.tipo == "alumno" else "home")
    else:
        form = RegistroUsuarioForm()
    return render(request, "registro.html", {"form": form})

def iniciar_sesion(request):
    if request.method == "POST":
        correo = request.POST['email']
        contraseña = request.POST['password']
        user = authenticate(request, username=correo, password=contraseña)
        if user:
            login(request, user)
            return redirect("alumno" if user.tipo == "alumno" else "home")
    return render(request, "login.html")

def cerrar_sesion(request):
    logout(request)
    return redirect('login')

def home(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    return render(request, 'home.html')


def descargar_archivo(request):
    calificacion_id = request.GET.get('id')

    try:
        calificacion = Calificaciones.objects.get(id=calificacion_id)
        if calificacion.archivoTarea:
            response = HttpResponse(calificacion.archivoTarea, content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename={calificacion.nombre_archivo}'
            return response
        else:
            raise Http404("Archivo no encontrado.")
    except Calificaciones.DoesNotExist:
        raise Http404("Calificación no encontrada.")
    
def alumno(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    usuario = Usuario.objects.get(id=request.user.id)
    
    # Obtener el equipo del usuario logueado
    equipo = Equipos.objects.filter(id=usuario.idEquipo).first()
    
    # Obtener todos los usuarios del equipo, excluyendo al usuario logueado
    usuarios_equipo = Usuario.objects.filter(idEquipo=usuario.idEquipo).exclude(id=usuario.id).exclude(idEquipo = None)
    
    
    # Obtener los registros del calendario
    actividades = obtener_actividades_filtradas(request)
    ids = [a.id for a in actividades]
    calendario = Calendario.objects.filter(idActividad__in = ids)
    
    suma = 0
    
    fecha_actual = datetime.now()
    for cal in calendario:
        puede_subir = True
        ids = obtener_usuarios_de_mi_equipo(request)
        calificacion = Calificaciones.objects.filter( idActividad = cal.idActividad.id, idUsuario__in = ids ).first()

        if calificacion:
            puede_subir = False
            suma = suma + calificacion.Calificacion
        
        if datetime.now() > datetime.combine(cal.Fecha_limite, datetime.min.time()):
            puede_subir = False

        cal.calificacion = calificacion
        cal.puede_subir = puede_subir
        cal.bg_color = "bg-cute-" + cal.idActividad.ro_responsable.replace(' ', '-')
    
    Completado = 0
    if( len(calendario) > 0):
        Completado = round(suma / len(calendario), 2)



    for miembro in usuarios_equipo:
        miembro.bg_color = "bg-cute-" + miembro.rol.replace(' ', '-')


    return render(request, "alumno.html", {
        "usuario": usuario,
        "equipo": equipo,
        "calendario": calendario,
        "Completado": Completado,
        "Restante": 100 - Completado,
        "usuarios_equipo": usuarios_equipo,
        'today': date.today()
    })

@csrf_exempt
def agrega_grupo(request):
    if request.method == "POST":
        data = json.loads(request.body)
        grupo = Grupos.objects.create(Nombre=data["Nombre"])
        if "usuarios" in data:
            usuarios = Usuario.objects.filter(id__in=data["usuarios"])
            for usuario in usuarios:
                usuario.idGrupo = grupo.id
                usuario.save()

                Notificacion.objects.create(
                    texto="Se te ha asignado a un grupo",
                    idAlumno=usuario.id,
                    visto=False
                )
        return JsonResponse({"id": grupo.id, "Nombre": grupo.Nombre})

@csrf_exempt
def agregar_equipo(request):
    if request.method == "POST":
        data = json.loads(request.body)
        equipo = Equipos.objects.create(Nombre=data["Nombre"], idGrupo=data["idGrupo"])
        if "usuarios" in data:
            usuarios = Usuario.objects.filter(id__in=data["usuarios"])
            for usuario in usuarios:
                usuario.idEquipo = equipo.id
                usuario.idGrupo = data["idGrupo"]
                usuario.save()
        

    for alumno in usuarios:
        Notificacion.objects.create(
            texto="Se ha creado un nuevo grupo",
            idAlumno=alumno.id,
            visto=False
        )

        return JsonResponse({"id": equipo.id, "Nombre": equipo.Nombre})

@csrf_exempt
def agregar_actividad(request):
    if request.method == "POST":
        data = json.loads(request.body)

        if "id" in data and data["id"] != '':
            # Actualizar actividad existente
            actividad = Actividades.objects.get(id=data["id"])
            actividad.Nombre = data["Nombre"]
            actividad.Descripcion = data["Descripcion"]
            actividad.tipo = data["tipo"]
            actividad.hora_limite = data["hora_limite"]
            actividad.objetivo = data["objetivo_actividad"]
            actividad.ro_responsable = data["ro_responsable"]
            actividad.id_creador = request.user.id
            actividad.save()

            # Actualizar fecha en Calendario
            fecha_actividad = datetime.strptime(data["Fecha_limite"], "%Y-%m-%d").date()
            calendario, _ = Calendario.objects.get_or_create(idActividad=actividad)
            calendario.Fecha_limite = fecha_actividad
            calendario.save()

            # Eliminar preguntas y respuestas previas
            Preguntas.objects.filter(idActividad=actividad.id).delete()

        else:
            # Crear nueva actividad
            actividad = Actividades.objects.create(
                Nombre=data["Nombre"],
                Descripcion=data["Descripcion"],
                tipo=data["tipo"],
                hora_limite=data["hora_limite"],
                objetivo=data["objetivo_actividad"],
                ro_responsable=data["ro_responsable"],
                id_creador = request.user.id
            )
            fecha_actividad = datetime.strptime(data["Fecha_limite"], "%Y-%m-%d").date()
            Calendario.objects.create(idActividad=actividad, Fecha_limite=fecha_actividad)

            alumnos = Usuario.objects.filter(tipo="alumno", rol = data["ro_responsable"])
            for alumno in alumnos:
                Notificacion.objects.create(
                    texto="Se ha agregado una nueva actividad",
                    idAlumno=alumno.id,
                    visto=False
                )

        if data["tipo"] == "Quizz":
            for pregunta_data in data["preguntas"]:
                pregunta = Preguntas.objects.create(idActividad=actividad.id, Texto=pregunta_data["pregunta"])
                for respuesta_data in pregunta_data["respuestas"]:
                    Respuestas.objects.create(idPregunta=pregunta.id, Texto=respuesta_data["Texto"], eslaCorrecta=respuesta_data["eslaCorrecta"])

        return JsonResponse({"id": actividad.id, "Nombre": actividad.Nombre})


def obtener_grupos(request):
    grupos = list(Grupos.objects.values())
    return JsonResponse(grupos, safe=False)

def obtener_grupo(request, id):
    grupo = get_object_or_404(Grupos, id=id)
    alumnos = Usuario.objects.filter(idGrupo=id).values()

    for alumno in alumnos:
        promedio = Calificaciones.objects.filter(idUsuario = alumno["id"]).aggregate(promedio=Avg('Calificacion'))['promedio']
        alumno["promedio"] = promedio

    return JsonResponse({"id": grupo.id, "Nombre": grupo.Nombre, "Alumnos": list(alumnos)})

def obtener_equipos(request, idGrupo):
    equipos = Equipos.objects.filter(idGrupo=idGrupo).values()
    equipos_lista = []
    for equipo in equipos:
        alumnos = Usuario.objects.filter(idEquipo=equipo["id"]).values()
        for alumno in alumnos:
            alumno["Calificaciones"] = list(Calificaciones.objects.filter(idUsuario=alumno["id"]).values())
        equipos_lista.append({"Equipo": equipo, "Alumnos": list(alumnos)})
    return JsonResponse(equipos_lista, safe=False)

def obtener_equipo(request, idEquipo):
    equipo = get_object_or_404(Equipos, id=idEquipo)
    alumnos = Usuario.objects.filter(idEquipo=idEquipo).values()
    for alumno in alumnos:
        alumno["Calificaciones"] = list(Calificaciones.objects.filter(idUsuario=alumno["id"]).values())
    return JsonResponse({"id": equipo.id, "Nombre": equipo.Nombre, "Alumnos": list(alumnos)})


def obtener_usuarios_de_mi_equipo(request):
    usuario = Usuario.objects.get(id=request.user.id)
    
    # Obtener el equipo del usuario logueado
    usuarios = Usuario.objects.filter(idEquipo = usuario.idEquipo)
    ids = [u.id for u in usuarios]

    return ids


def obtener_actividades_filtradas(request):
    usuario = Usuario.objects.get(id=request.user.id)
    ids = obtener_usuarios_de_mi_equipo(request)

    if usuario.tipo == "maestro":
        actvs = Actividades.objects.all()
    else:
        if usuario.rol == "Maestro de Scrum":
            actvs = Actividades.objects.filter(Q(id_creador__in=ids) | Q(ro_responsable="Maestro de Scrum") | Q(ro_responsable = "Todos"))
        else:
            actvs = Actividades.objects.filter(Q(ro_responsable = usuario.rol) | Q(ro_responsable = "Todos"))

    return actvs 


def obtener_actividades(request):
    actividades_data = []

    actividades = obtener_actividades_filtradas(request)

    for actividad in actividades:
        calendario = Calendario.objects.filter(idActividad=actividad).first()
        calificacion = Calificaciones.objects.filter(idActividad=actividad.id).first()

        actividades_data.append({
            "id": actividad.id,
            "Nombre": actividad.Nombre,
            "Descripcion": actividad.Descripcion,
            "tipo": actividad.tipo,
            "ro_responsable": actividad.ro_responsable,
            "fecha_limite": calendario.Fecha_limite.strftime('%Y-%m-%d') if calendario else None,
            "calificacion": calificacion.Calificacion if calificacion else None
        })

    return JsonResponse(actividades_data, safe=False)


@csrf_exempt
def eliminar_actividad(request):
    if request.method == "POST":
        data = json.loads(request.body)
        actividad_id = data.get("id")
        try:
            actividad = Actividades.objects.get(id=actividad_id)
            actividad.delete()
            return JsonResponse({"mensaje": "Actividad eliminada correctamente"})
        except Actividades.DoesNotExist:
            return JsonResponse({"error": "Actividad no encontrada"}, status=404)
    return JsonResponse({"error": "Método no permitido"}, status=405)

def obtener_actividad(request):
    actividad_id = request.GET.get('id')
    actividad = Actividades.objects.get(id=actividad_id)
    
    # Obtener preguntas y respuestas
    preguntas = []
    for pregunta in Preguntas.objects.filter(idActividad=actividad_id):
        respuestas = []
        for respuesta in Respuestas.objects.filter(idPregunta=pregunta.id):
            respuestas.append({
                "id": respuesta.id,
                'texto': respuesta.Texto,
                'eslaCorrecta': respuesta.eslaCorrecta
            })
        preguntas.append({
            "id": pregunta.id,
            'texto': pregunta.Texto,
            'respuestas': respuestas
        })
    
    # Obtener el calendario relacionado con la actividad
    calendario = Calendario.objects.filter(idActividad=actividad_id).first()
    fecha_limite = calendario.Fecha_limite if calendario else None

    # Enviar los datos como JSON
    return JsonResponse({
        'tipo': actividad.tipo,
        'nombre': actividad.Nombre,
        'descripcion': actividad.Descripcion,
        'preguntas': preguntas,
        'fecha_limite': fecha_limite,
        'hora_limite': actividad.hora_limite,
        'objetivo': actividad.objetivo,
        'ro_responsable': actividad.ro_responsable
    })

@csrf_exempt
def obtener_calendario(request):

    actividades = obtener_actividades_filtradas(request)
    ids = [a.id for a in actividades]


    start_date = request.GET.get("start")
    end_date = request.GET.get("end")

    if start_date and end_date:
        start_date = datetime.fromisoformat(start_date[:-6]).date()  # Remueve la zona horaria
        end_date = datetime.fromisoformat(end_date[:-6]).date()  # Remueve la zona horaria
        eventos = Calendario.objects.filter(Fecha_limite__range=[start_date, end_date], idActividad__in = ids)
    else:
        eventos = Calendario.objects.all(idActividad__in = ids)

    colores_x_rol = {
        "Maestro de Scrum": "#e36282",
        "Desarrollador 1": "#1aa5a1",
        "Desarrollador 2": "#61c14d",
        "Propietario del Producto": "#b9a741",
        "Todos": "#333"
    }
    
    eventos_json = [
        {
            "id": evento.idActividad.id,
            "title": evento.idActividad.Nombre,
            "start": evento.Fecha_limite.isoformat(),
            "end": evento.Fecha_limite.isoformat(),
            "extendedProps": {
                "descripcion": evento.idActividad.Descripcion
            },
            "className": "bg-cute-" + evento.idActividad.ro_responsable.replace(' ', '-'),
            "textColor": colores_x_rol.get(evento.idActividad.ro_responsable, "")

        }
        for evento in eventos
    ]

    return JsonResponse(eventos_json, safe=False)

def obtener_alumnos(request):
    alumnos = list(Usuario.objects.filter(tipo="alumno").values())
    return JsonResponse(alumnos, safe=False)
    
@csrf_exempt
def guardar_tarea(request):
    if request.method == "POST":
        try:
            data = request.POST
            id_actividad = data.get("idActividad")
            actividad = Actividades.objects.get(id=id_actividad)
            usuario = request.user  # Suponiendo que el usuario está autenticado

            if actividad.tipo == "Quizz":
                respuestas_json = json.loads(data.get("respuestas", "[]"))
                correctas = 0
                total = len(respuestas_json)
                for respuesta in respuestas_json:
                    respuesta_obj = Respuestas.objects.get(id=respuesta["idRespuesta"])
                    if respuesta_obj.eslaCorrecta:  # Comprobar si la respuesta es correcta
                        correctas += 1

                    Respuestas_Alumno.objects.create(
                        idPregunta=respuesta["idPregunta"],
                        idRespuesta=respuesta["idRespuesta"]
                    )

                if total > 0:
                    promedio = correctas / total
                else:
                    promedio = 0

                calificacion, _ = Calificaciones.objects.get_or_create(
                    idUsuario=usuario.id, idActividad=actividad.id,
                    Calificacion = 100 * promedio
                )
                calificacion.save()
            else:
                archivo = request.FILES.get("archivo")
                if archivo:
                    archivo_bytes = archivo.read()
                    nombre_archivo = archivo.name
                    extension_archivo = nombre_archivo.split('.')[-1] if '.' in nombre_archivo else ''

                    calificacion, _ = Calificaciones.objects.get_or_create(
                        idUsuario=usuario.id, idActividad=actividad.id,
                        Calificacion = 100
                    )
                    calificacion.archivoTarea = archivo_bytes
                    calificacion.descripcion_tarea = data.get("descripcion_tarea")
                    calificacion.nombre_archivo = nombre_archivo
                    calificacion.extension_archivo = extension_archivo
                    calificacion.save()

            return JsonResponse({"mensaje": "Tarea guardada correctamente"}, status=200)

        except Actividades.DoesNotExist:
            return JsonResponse({"error": "Actividad no encontrada"}, status=404)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
def revolver_roles(request):
    


    if request.method == 'POST':
        # Obtener el id del grupo
        id_grupo = request.POST.get('idGrupo')

        if not id_grupo:
            return JsonResponse({'error': 'ID de grupo no proporcionado'}, status=400)

        # Obtener todos los usuarios del grupo
        usuarios = Usuario.objects.filter(idGrupo=id_grupo)

        # Agrupar usuarios por idEquipo
        equipos = {}
        for usuario in usuarios:
            if usuario.idEquipo not in equipos:
                equipos[usuario.idEquipo] = []
            equipos[usuario.idEquipo].append(usuario)

        # Roles disponibles
        roles = ['Maestro de Scrum', 'Propietario del Producto', 'Desarrollador 1', 'Desarrollador 2']

        # Asignar roles aleatorios a los usuarios de cada equipo
        for id_equipo, miembros in equipos.items():
            # Si hay menos de 4 miembros, el rol de "Developer" será asignado aleatoriamente
            random.shuffle(roles)  # Barajar los roles

            for i, miembro in enumerate(miembros):
                if i < len(roles):
                    miembro.rol = roles[i]
                    miembro.save()  # Guardar el rol asignado al usuario
            
            for alumno in usuarios:
                Notificacion.objects.create(
                    texto="Se te ha asignado un nuevo Rol",
                    idAlumno=alumno.id,
                    visto=False
                )
        return JsonResponse({'message': 'Roles revueltos con éxito.'})

    return JsonResponse({'error': 'Método no permitido'}, status=405)

def obtener_notificaciones(request):
    notificaciones = Notificacion.objects.filter(
        idAlumno=request.user.id).order_by('-fechaEnvio')[:10].values('id', 'texto', 'fechaEnvio', 'visto')

    return JsonResponse(list(notificaciones), safe=False)

def marcar_notificaciones_como_vistas(request):
    Notificacion.objects.filter(idAlumno=request.user.id).update(visto=True)
    return JsonResponse({"status": "ok"})



