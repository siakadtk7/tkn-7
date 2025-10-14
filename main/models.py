from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
import os
import uuid

# ======================
# Upload Path Functions
# ======================
def siswa_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f'{uuid.uuid4()}.{ext}'
    return os.path.join('siswa', filename)

def guru_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f'{uuid.uuid4()}.{ext}'
    return os.path.join('guru', filename)

def laporan_aspek_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f'{uuid.uuid4()}.{ext}'
    return os.path.join('laporan_foto', filename)


# ======================
# Model Profile
# ======================
class Profile(models.Model):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('guru', 'Guru'),
        ('kepala', 'Kepala Sekolah'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    def __str__(self):
        return f"{self.user.username} - {self.role}"

# otomatis buat Profile ketika User dibuat
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # Set default role to 'admin' for new users, or 'kepala' if that's the intended default for superusers
        Profile.objects.create(user=instance, role='admin') # Default to 'admin'

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()


# ======================
# Tahun Ajaran
# ======================
class TahunAjaran(models.Model):
    nama = models.CharField(max_length=20)  # Contoh: "2025/2026"
    is_active = models.BooleanField(default=False)  # Tahun ajaran berjalan
    mulai = models.DateField(blank=True, null=True)
    selesai = models.DateField(blank=True, null=True)


# ======================
# Model Refleksi Komentar
# ======================
class RefleksiKomentar(models.Model):
    teks = models.TextField()
    tahun_ajaran = models.ForeignKey(TahunAjaran, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    refleksi_global = models.TextField(blank=True, null=True) # Keep this field

    def __str__(self):
        return f"{self.tahun_ajaran.nama} - {self.teks[:50]}"



# ======================
# Model Siswa
# ======================
class Siswa(models.Model):
    nama = models.CharField(max_length=100)
    nisn = models.CharField(max_length=20, unique=True)
    nomor_induk = models.CharField(max_length=20, unique=True)
    jenis_kelamin = models.CharField(max_length=1, choices=[('L', 'Laki-laki'), ('P', 'Perempuan')])
    kelas = models.ForeignKey('Kelas', on_delete=models.SET_NULL, null=True, blank=True)
    tahun_ajaran = models.CharField(max_length=20)
    tempat_lahir = models.CharField(max_length=50, blank=True, null=True)
    tanggal_lahir = models.DateField(blank=True, null=True)
    agama = models.CharField(max_length=30, blank=True, null=True)
    nama_ayah = models.CharField(max_length=100, blank=True, null=True)
    nama_ibu = models.CharField(max_length=100, blank=True, null=True)
    alamat = models.TextField(blank=True, null=True)
    no_hp = models.CharField(max_length=15, blank=True, null=True)
    foto = models.ImageField(upload_to=siswa_upload_path, blank=True, null=True)

    def __str__(self):
        return self.nama

@receiver(post_delete, sender=Siswa)
def delete_siswa_foto(sender, instance, **kwargs):
    if instance.foto:
        if os.path.isfile(instance.foto.path):
            os.remove(instance.foto.path)


# ======================
# Model Guru
# ======================
class Guru(models.Model):
    JABATAN_CHOICES = [
        ('kepala_sekolah', 'Kepala Sekolah'),
        ('tata_usaha', 'Tata Usaha'),
        ('wali_kelas', 'Wali Kelas'),
        ('guru', 'Guru'),
        ('pengawas_tk', 'Pengawas TK'),
        ('komite_sekolah', 'Komite Sekolah'),
    ]
    nama = models.CharField(max_length=100)
    nip = models.CharField(max_length=50, unique=True, blank=True, null=True)
    jabatan = models.CharField(max_length=20, choices=JABATAN_CHOICES)
    tempat_lahir = models.CharField(max_length=100)
    tanggal_lahir = models.DateField()
    tanggal_masuk = models.DateField()
    alamat = models.TextField()
    no_telp = models.CharField(max_length=20)
    foto = models.ImageField(upload_to=guru_upload_path, blank=True, null=True)
    tahun_ajaran = models.ForeignKey(TahunAjaran, on_delete=models.SET_NULL, null=True, blank=True)
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True)


    def __str__(self):
        return f"{self.nama} - {self.get_jabatan_display()}"

@receiver(post_delete, sender=Guru)
def delete_guru_foto(sender, instance, **kwargs):
    if instance.foto:
        if os.path.isfile(instance.foto.path):
            os.remove(instance.foto.path)



# ======================
# Model Laporan Perkembangan
# ======================
class LaporanPerkembangan(models.Model):
    siswa = models.ForeignKey(Siswa, on_delete=models.CASCADE)
    tanggal = models.DateField(auto_now_add=True)
    semester = models.CharField(max_length=10, choices=[('1', 'Semester 1'), ('2', 'Semester 2')])
    status = models.CharField(max_length=10, choices=[('siap', 'Siap'), ('belum', 'Belum')])
    refleksi_orang_tua = models.TextField(blank=True, null=True) # Field baru
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.siswa.nama} - Semester {self.semester}"

class AspekPerkembangan(models.Model):
    tahun_ajaran = models.ForeignKey(TahunAjaran, on_delete=models.CASCADE, related_name='aspek_perkembangan', null=True, blank=True)
    nama_aspek = models.CharField(max_length=100)
    deskripsi = models.TextField(default='')

    def __str__(self):
        return f"{self.nama_aspek} ({self.tahun_ajaran})"

class LaporanAspek(models.Model):
    laporan = models.ForeignKey(LaporanPerkembangan, related_name='aspek', on_delete=models.CASCADE)
    aspek = models.ForeignKey(AspekPerkembangan, on_delete=models.PROTECT, null=True)
    deskripsi = models.TextField(blank=True, null=True)
    foto = models.ImageField(upload_to=laporan_aspek_upload_path, blank=True, null=True)

    def __str__(self):
        return f"{self.laporan.siswa.nama} - {self.aspek.nama_aspek}"

@receiver(post_delete, sender=LaporanAspek)
def delete_laporan_aspek_foto(sender, instance, **kwargs):
    if instance.foto:
        if os.path.isfile(instance.foto.path):
            os.remove(instance.foto.path)



# ======================
# Model Kelas
# ======================
class Kelas(models.Model):
    nama = models.CharField(max_length=100, unique=True)
    wali_kelas = models.ForeignKey(Guru, on_delete=models.SET_NULL, null=True, blank=True, limit_choices_to={'jabatan': 'wali_kelas'})

    def __str__(self):
        return self.nama


# ======================
# Model Absensi
# ======================
class Absensi(models.Model):
    STATUS_CHOICES = [
        ('Hadir', 'Hadir'),
        ('Sakit', 'Sakit'),
        ('Izin', 'Izin'),
        ('Alpa', 'Tanpa Keterangan'),
    ]

    siswa = models.ForeignKey(Siswa, on_delete=models.CASCADE)
    tanggal = models.DateField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    class Meta:
        unique_together = ('siswa', 'tanggal')  # agar satu siswa per tanggal hanya 1 record

    def __str__(self):
        return f"{self.siswa.nama} - {self.tanggal} - {self.status}"

