from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

class UsuarioManager(BaseUserManager):
    def create_user(self, email, username, password=None, tipo="alumno"):
        if not email:
            raise ValueError("El usuario debe tener un correo electrónico")
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, tipo=tipo)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None):
        user = self.create_user(email, username, password)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user

class Usuario(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    idGrupo = models.IntegerField(blank=True, null=True)
    idEquipo = models.IntegerField(blank=True, null=True)
    rol = models.CharField(max_length=100, blank=True, null=True, choices=[('Maestro de Scrum', 'Maestro de Scrum'), ('Propietario del Producto', 'Propietario del Producto'), ('Desarrollador 1', 'Desarrollador 1'), ('Desarrollador 2', 'Desarrollador 2')])
    tipo = models.CharField(max_length=10, choices=[('alumno', 'Alumno'), ('maestro', 'Maestro')], default='alumno')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UsuarioManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email

from django.db import models

class Notificacion(models.Model):
    texto = models.TextField()
    fechaEnvio = models.DateTimeField(auto_now_add=True)
    idAlumno = models.IntegerField()  # Nueva columna
    visto = models.BooleanField(default=False)  # Nueva columna


class Calificaciones(models.Model):
    idUsuario = models.IntegerField()
    idActividad = models.IntegerField()
    Calificacion = models.DecimalField(max_digits=5, decimal_places=2)
    archivoTarea = models.BinaryField(null=True, blank=True)
    descripcion_tarea = models.CharField(max_length=5000, default="")
    nombre_archivo = models.CharField(max_length=100, default="")
    extension_archivo = models.CharField(max_length=100, default="")

class Actividades(models.Model):
    Nombre = models.TextField()
    Descripcion = models.TextField()
    tipo = models.TextField()
    hora_limite = models.CharField(max_length=5, default="00")
    objetivo = models.CharField(max_length=5000, default="")
    id_creador = models.IntegerField()
    ro_responsable = models.CharField(max_length=100, default="Maestro de Scrum")

class Preguntas(models.Model):
    idActividad = models.IntegerField()
    Texto = models.TextField()

class Respuestas(models.Model):
    idPregunta = models.IntegerField()
    Texto = models.TextField()
    eslaCorrecta = models.BooleanField()

class Grupos(models.Model):
    Nombre = models.TextField()

class Respuestas_Alumno(models.Model):
    idPregunta = models.IntegerField()
    idRespuesta = models.IntegerField()

class Equipos(models.Model):
    Nombre = models.TextField()
    idGrupo = models.IntegerField()

class Calendario(models.Model):
    idActividad = models.ForeignKey(Actividades, on_delete=models.CASCADE)
    Fecha_limite = models.DateField()
