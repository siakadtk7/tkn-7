from django.shortcuts import get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
import weasyprint

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, ProtectedError
from django.db import IntegrityError
from django.template.loader import render_to_string, get_template
from datetime import date, datetime, timedelta
from django.utils import timezone
import json
import locale
from calendar import monthrange
from django.conf import settings
import google.generativeai as genai
import os

from .models import Siswa, Guru, Profile, Kelas, Absensi, TahunAjaran, LaporanPerkembangan, AspekPerkembangan, LaporanAspek, RefleksiKomentar
import weasyprint
from weasyprint import HTML
import tempfile

from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, UserChangeForm

from django.views.decorators.http import require_http_methods
from .forms import RefleksiOrangTuaForm

from collections import OrderedDict

# ------------------------
# LOGIN / LOGOUT
# ------------------------
def login_view(request):
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            role = user.profile.role
            if role == 'admin':
                return redirect('admin_dashboard')
            elif role == 'guru':
                return redirect('guru_dashboard')
            elif role == 'kepala':
                return redirect('kepala_dashboard')
        else:
            messages.error(request, "Username atau password salah!")
    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


# ------------------------
# ROOT REDIRECT
# ------------------------
def root_redirect(request):
    if request.user.is_authenticated:
        role = request.user.profile.role
        if role == 'admin':
            return redirect('admin_dashboard')
        elif role == 'guru':
            return redirect('guru_dashboard')
        elif role == 'kepala':
            return redirect('kepala_dashboard')
    return redirect('login')



# ------------------------
# DASHBOARD GURU
# ------------------------
def guru_dashboard(request):
    user = request.user
    role = getattr(user.profile, 'role', None)

    today = date.today()

    # Kehadiran harian
    absensi_hari_ini = Absensi.objects.filter(tanggal=today)
    hadir = absensi_hari_ini.filter(status='Hadir').count()
    sakit = absensi_hari_ini.filter(status='Sakit').count()
    izin = absensi_hari_ini.filter(status='Izin').count()
    tanpa_keterangan = absensi_hari_ini.filter(status='Alpa').count()

    # Kehadiran bulanan
    bulan = request.GET.get('bulan')
    if bulan:
        tahun, bulan_int = map(int, bulan.split('-'))
    else:
        tahun, bulan_int = today.year, today.month

    # ===== Role-based filtering untuk siswa_list =====
    siswa_list = Siswa.objects.all() # Queryset awal
    if role == 'guru':
        try:
            guru_instance = Guru.objects.get(user=user)
            kelas_terpilih = Kelas.objects.get(wali_kelas=guru_instance)
            siswa_list = siswa_list.filter(kelas=kelas_terpilih) # Filter siswa berdasarkan kelas wali kelas
        except (Guru.DoesNotExist, Kelas.DoesNotExist, Kelas.MultipleObjectsReturned):
            messages.error(request, "Data guru atau kelas Anda tidak ditemukan.")
            siswa_list = Siswa.objects.none() # Jika tidak ditemukan, tampilkan queryset kosong
    # =====================================================================

    bulan_nama = datetime(tahun, bulan_int, 1).strftime("%B %Y")

    data_bulanan = []
    for siswa in siswa_list: # Gunakan siswa_list yang sudah difilter
        absensi_bulan = Absensi.objects.filter(siswa=siswa, tanggal__year=tahun, tanggal__month=bulan_int)
        data_bulanan.append({
            'nama': siswa.nama,
            'Hadir': absensi_bulan.filter(status='Hadir').count(),
            'Sakit': absensi_bulan.filter(status='Sakit').count(),
            'Izin': absensi_bulan.filter(status='Izin').count(),
            'Alpa': absensi_bulan.filter(status='Alpa').count(),
        })

    # Get active academic year
    try:
        active_tahun_ajaran_obj = TahunAjaran.objects.get(is_active=True)
        active_tahun_ajaran_name = active_tahun_ajaran_obj.nama
    except TahunAjaran.DoesNotExist:
        active_tahun_ajaran_name = tahun_ajaran_berjalan() # Fallback if no active year is set

    # Student Data for Pie Chart (by gender for active academic year)
    # Gunakan siswa_list yang sudah difilter untuk total_siswa, siswa_laki_laki, siswa_perempuan
    siswa_active_ta = siswa_list.filter(tahun_ajaran=active_tahun_ajaran_name)
    total_siswa = siswa_active_ta.count()
    siswa_laki_laki = siswa_active_ta.filter(jenis_kelamin='L').count()
    siswa_perempuan = siswa_active_ta.filter(jenis_kelamin='P').count()

    # Daily Attendance Data for Line Chart (current month)
    today = timezone.now().date()
    first_day_of_month = today.replace(day=1)
    last_day_of_month = today.replace(day=monthrange(today.year, today.month)[1])

    daily_attendance_data = Absensi.objects.filter(
        tanggal__year=today.year,
        tanggal__month=today.month,
        status='Hadir',
        siswa__in=siswa_list # Filter berdasarkan siswa_list yang sudah difilter
    ).values('tanggal').annotate(hadir_count=Count('id')).order_by('tanggal')

    # Prepare dates and counts for the entire month
    dates = []
    hadir_counts = []
    current_day = first_day_of_month
    while current_day <= last_day_of_month:
        dates.append(current_day.strftime('%Y-%m-%d'))
        hadir_counts.append(0) # Initialize with 0
        current_day += timedelta(days=1)

    # Populate hadir_counts with actual data
    for data in daily_attendance_data:
        try:
            index = (data['tanggal'] - first_day_of_month).days
            if 0 <= index < len(dates):
                hadir_counts[index] = data['hadir_count']
        except OverflowError:
            pass

    context = {
        'hadir': hadir,
        'sakit': sakit,
        'izin': izin,
        'tanpa_keterangan': tanpa_keterangan,
        'data_bulanan': data_bulanan,
        'bulan_nama': bulan_nama,
        'total_siswa': total_siswa,
        'siswa_laki_laki': siswa_laki_laki,
        'siswa_perempuan': siswa_perempuan,
        'attendance_dates': json.dumps(dates),
        'attendance_hadir_counts': json.dumps(hadir_counts),
    }
    return render(request, 'guru_dashboard.html', context)


# ------------------------
# DASHBOARD KEPALA
# -----------------------
@login_required
def kepala_dashboard(request):
    # Guru Data for Chart (by Jabatan)
    guru_data = Guru.objects.values('jabatan').annotate(count=Count('id')).order_by('jabatan')
    guru_labels = [item['jabatan'] for item in guru_data]
    guru_counts = [item['count'] for item in guru_data]

    # Siswa Data for Chart (by gender for active academic year)
    try:
        active_tahun_ajaran_obj = TahunAjaran.objects.get(is_active=True)
        active_tahun_ajaran_name = active_tahun_ajaran_obj.nama
    except TahunAjaran.DoesNotExist:
        active_tahun_ajaran_name = tahun_ajaran_berjalan() # Fallback

    siswa_active_ta = Siswa.objects.filter(tahun_ajaran=active_tahun_ajaran_name)
    total_siswa = siswa_active_ta.count()
    siswa_laki_laki = siswa_active_ta.filter(jenis_kelamin='L').count()
    siswa_perempuan = siswa_active_ta.filter(jenis_kelamin='P').count()

    context = {
        'guru_labels': json.dumps(guru_labels),
        'guru_counts': json.dumps(guru_counts),
        'total_siswa': total_siswa,
        'siswa_laki_laki': siswa_laki_laki,
        'siswa_perempuan': siswa_perempuan,
    }
    return render(request, 'kepala_dashboard.html', context)


# ------------------------
# DASHBOARD ADMIN
# ------------------------
def dashboard_admin(request):
    # ===== Tahun ajaran berjalan =====
    today = date.today()
    if today.month >= 7:
        start_year = today.year
        end_year = today.year + 1
    else:
        start_year = today.year - 1
        end_year = today.year
    tahun_ajaran = f'{start_year}/{end_year}'

    # ===== Jumlah siswa putra/putri =====
    siswa_qs = Siswa.objects.filter(tahun_ajaran=tahun_ajaran)
    jumlah_putra = siswa_qs.filter(jenis_kelamin='L').count()
    jumlah_putri = siswa_qs.filter(jenis_kelamin='P').count()

    # ===== Absensi Bulan Berjalan =====
    bulan_ini = today.month
    tahun_ini = today.year
    hari_terakhir = monthrange(tahun_ini, bulan_ini)[1]

    absensi_bulan = {}
    for hari in range(1, hari_terakhir + 1):
        tgl = date(tahun_ini, bulan_ini, hari)
        hadir = Absensi.objects.filter(tanggal=tgl, status='Hadir').count()
        izin = Absensi.objects.filter(tanggal=tgl, status='Izin').count()
        sakit = Absensi.objects.filter(tanggal=tgl, status='Sakit').count()
        alpha = Absensi.objects.filter(tanggal=tgl, status='Alpha').count()
        absensi_bulan[tgl.strftime('%Y-%m-%d')] = {
            'Hadir': hadir,
            'Izin': izin,
            'Sakit': sakit,
            'Alpha': alpha
        }

    context = {
        'jumlah_putra': jumlah_putra,
        'jumlah_putri': jumlah_putri,
        'absensi_bulan': absensi_bulan,
        'bulan': today,
    }
    return render(request, 'admin_dashboard.html', context)


# ------------------------
# DATA SISWA
# ------------------------
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

def data_siswa(request):
    user = request.user
    role = getattr(user.profile, 'role', None)

    q = request.GET.get('q', '')
    jenis_kelamin = request.GET.get('jenis_kelamin', '')
    tahun_ajaran = request.GET.get('tahun_ajaran')
    kelas_id = request.GET.get('kelas')

    if not tahun_ajaran:
        tahun_ajaran = tahun_ajaran_berjalan()

    wali_kelas_list = Guru.objects.all()
    kelas_terpilih = None

    # Base queryset
    siswa_list = Siswa.objects.all().order_by('nama')

    # Apply filters that affect the base student list
    if q:
        siswa_list = siswa_list.filter(
            Q(nama__icontains=q) |
            Q(nisn__icontains=q) |
            Q(nomor_induk__icontains=q)
        )
    if jenis_kelamin:
        siswa_list = siswa_list.filter(jenis_kelamin=jenis_kelamin)
    if tahun_ajaran:
        siswa_list = siswa_list.filter(tahun_ajaran=tahun_ajaran)

    # ===== Role-based filtering =====
    if role == 'guru':
        try:
            # Pastikan guru yang login memiliki objek Guru yang terkait
            guru_instance = Guru.objects.get(user=user)
            kelas_terpilih = Kelas.objects.get(wali_kelas=guru_instance)
            siswa_list = siswa_list.filter(kelas=kelas_terpilih) # Filter siswa berdasarkan kelas wali kelas
            kelas_id = kelas_terpilih.id # Set kelas_id agar dropdown kelas terpilih
            kelas_list = Kelas.objects.filter(id=kelas_terpilih.id) # Hanya tampilkan kelas guru tersebut di dropdown
        except (Guru.DoesNotExist, Kelas.DoesNotExist, Kelas.MultipleObjectsReturned):
            messages.error(request, "Data guru atau kelas Anda tidak ditemukan.")
            siswa_list = Siswa.objects.none() # Jika tidak ditemukan, tampilkan queryset kosong
            kelas_list = Kelas.objects.none() # Kosongkan daftar kelas
    
    elif role in ['admin', 'kepala']:
        # Determine the list of classes for the dropdown based on the filtered students
        if q and not request.GET.get('kelas'):
            # If searching, limit the class dropdown to classes from the search results
            kelas_ids = siswa_list.values_list('kelas_id', flat=True).distinct()
            kelas_list = Kelas.objects.filter(id__in=kelas_ids)

            # If the search results in a single class, pre-select it.
            if kelas_list.count() == 1:
                single_class = kelas_list.first()
                if single_class:
                    kelas_id = str(single_class.id) # Set/overwrite kelas_id
        else:
            # Otherwise, show all classes
            kelas_list = Kelas.objects.all()

        # Now, apply the class filter to the student list for the final result
        if kelas_id:
            siswa_list = siswa_list.filter(kelas_id=kelas_id)
            try:
                # Use the potentially updated kelas_id
                kelas_terpilih = Kelas.objects.get(id=int(kelas_id))
            except (Kelas.DoesNotExist, ValueError, TypeError):
                pass # Biarkan kelas_terpilih None
    # =====================================================

    # Pagination logic
    paginator = Paginator(siswa_list, 10)  # 10 students per page
    page_number = request.GET.get('page')
    try:
        siswa_page = paginator.page(page_number)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        siswa_page = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        siswa_page = paginator.page(paginator.num_pages)

    tahun_ajaran_list = Siswa.objects.values_list('tahun_ajaran', flat=True).distinct().order_by('-tahun_ajaran')
    read_only = request.user.profile.role == 'kepala'

    # For client-side validation
    existing_nomor_induk = {s.nomor_induk: s.id for s in Siswa.objects.all() if s.nomor_induk}
    existing_nisn = {s.nisn: s.id for s in Siswa.objects.all() if s.nisn}

    context = {
        'siswa_page': siswa_page,  # Pass the page object
        'tahun_ajaran_list': tahun_ajaran_list,
        'tahun_ajaran': tahun_ajaran,
        'read_only': read_only,
        'existing_nomor_induk_json': json.dumps(existing_nomor_induk),
        'existing_nisn_json': json.dumps(existing_nisn),
        'kelas_list': kelas_list,
        'wali_kelas_list': wali_kelas_list,
        'kelas_terpilih': kelas_terpilih,
        'kelas_id': kelas_id,
        'q': q,
    }
    return render(request, 'data_siswa.html', context)


@login_required
def siswa_tambah(request):
    if request.user.profile.role in ['guru', 'kepala']:
        messages.error(request, "Anda tidak memiliki akses untuk menambah data siswa.")
        return redirect(request.META.get('HTTP_REFERER', 'data_siswa'))
    if request.method == 'POST':
        # Ambil nilai, berikan None jika kosong untuk field yang bisa null
        tanggal_lahir_val = request.POST.get('tanggal_lahir')
        if not tanggal_lahir_val:
            tanggal_lahir_val = None

        try:
            Siswa.objects.create(
                nama=request.POST.get('nama'),
                nisn=request.POST.get('nisn'),
                nomor_induk=request.POST.get('nomor_induk'),
                jenis_kelamin=request.POST.get('jenis_kelamin'),
                kelas_id=request.POST.get('kelas_id'),
                tahun_ajaran=request.POST.get('tahun_ajaran'),
                tempat_lahir=request.POST.get('tempat_lahir'),
                tanggal_lahir=tanggal_lahir_val,
                agama=request.POST.get('agama'),
                nama_ayah=request.POST.get('nama_ayah'),
                nama_ibu=request.POST.get('nama_ibu'),
                alamat=request.POST.get('alamat'),
                no_hp=request.POST.get('no_hp'),
                foto=request.FILES.get('foto')
            )
            messages.success(request, f"Siswa '{request.POST.get('nama')}' berhasil ditambahkan.")
        except IntegrityError as e:
            if 'nomor_induk' in str(e):
                messages.error(request, f"Gagal menyimpan. Nomor Induk '{request.POST.get('nomor_induk')}' sudah digunakan.")
            elif 'nisn' in str(e):
                messages.error(request, f"Gagal menyimpan. NISN '{request.POST.get('nisn')}' sudah digunakan.")
            else:
                messages.error(request, f"Terjadi kesalahan yang tidak diketahui: {e}")
        
    return redirect(request.META.get('HTTP_REFERER', 'data_siswa'))


@login_required
def siswa_edit(request, pk):
    if request.user.profile.role in ['guru', 'kepala']:
        messages.error(request, "Anda tidak memiliki akses untuk mengubah data siswa.")
        return redirect(request.META.get('HTTP_REFERER', 'data_siswa'))
    siswa = get_object_or_404(Siswa, pk=pk)
    if request.method == 'POST':
        try:
            siswa.nama = request.POST.get('nama')
            siswa.nisn = request.POST.get('nisn')
            siswa.nomor_induk = request.POST.get('nomor_induk')
            siswa.jenis_kelamin = request.POST.get('jenis_kelamin')
            siswa.kelas_id = request.POST.get('kelas_id')
            siswa.tahun_ajaran = request.POST.get('tahun_ajaran')
            siswa.tempat_lahir = request.POST.get('tempat_lahir')
            
            tanggal_lahir_val = request.POST.get('tanggal_lahir')
            siswa.tanggal_lahir = tanggal_lahir_val if tanggal_lahir_val else None

            siswa.agama = request.POST.get('agama')
            siswa.nama_ayah = request.POST.get('nama_ayah')
            siswa.nama_ibu = request.POST.get('nama_ibu')
            siswa.alamat = request.POST.get('alamat')
            siswa.no_hp = request.POST.get('no_hp')
            if request.FILES.get('foto'):
                siswa.foto = request.FILES['foto']
            
            siswa.save()
            messages.success(request, f"Data siswa '{siswa.nama}' berhasil diperbarui.")

        except IntegrityError as e:
            if 'nomor_induk' in str(e):
                messages.error(request, f"Gagal menyimpan. Nomor Induk '{request.POST.get('nomor_induk')}' sudah digunakan oleh siswa lain.")
            elif 'nisn' in str(e):
                messages.error(request, f"Gagal menyimpan. NISN '{request.POST.get('nisn')}' sudah digunakan oleh siswa lain.")
            else:
                messages.error(request, f"Terjadi kesalahan yang tidak diketahui: {e}")

    return redirect(request.META.get('HTTP_REFERER', 'data_siswa'))


@login_required
def siswa_delete(request, pk):
    if request.user.profile.role in ['guru', 'kepala']:
        messages.error(request, "Anda tidak memiliki akses untuk menghapus data siswa.")
        return redirect('data_siswa')
    siswa = get_object_or_404(Siswa, pk=pk)
    siswa.delete()
    return redirect('data_siswa')


@login_required
def tambah_kelas(request):
    if request.user.profile.role in ['guru', 'kepala']:
        messages.error(request, "Anda tidak memiliki akses untuk menambah data kelas.")
        return redirect('data_siswa')
    if request.method == 'POST':
        nama_kelas = request.POST.get('nama_kelas')
        wali_kelas_id = request.POST.get('wali_kelas')

        if nama_kelas and wali_kelas_id:
            try:
                Kelas.objects.create(nama=nama_kelas, wali_kelas_id=wali_kelas_id)
                messages.success(request, f"Kelas '{nama_kelas}' berhasil ditambahkan.")
            except IntegrityError:
                messages.error(request, f"Kelas dengan nama '{nama_kelas}' sudah ada.")
        else:
            messages.error(request, "Nama kelas dan wali kelas harus diisi.")
            
    return redirect('data_siswa')


@login_required
def hapus_kelas(request, kelas_id):
    if request.user.profile.role in ['guru', 'kepala']:
        messages.error(request, "Anda tidak memiliki akses untuk menghapus data kelas.")
        return redirect('data_siswa')
    if request.method == 'POST':
        try:
            kelas = get_object_or_404(Kelas, id=kelas_id)
            nama_kelas = kelas.nama
            kelas.delete()
            messages.success(request, f"Kelas '{nama_kelas}' berhasil dihapus.")
        except ProtectedError:
            messages.error(request, "Kelas ini tidak bisa dihapus karena sudah ada siswa di dalamnya.")
        except Exception as e:
            messages.error(request, f"Terjadi kesalahan: {e}")
    return redirect('data_siswa')


@login_required
def edit_kelas(request, kelas_id):
    if request.user.profile.role in ['guru', 'kepala']:
        messages.error(request, "Anda tidak memiliki akses untuk mengubah data kelas.")
        return redirect('data_siswa')
    if request.method == 'POST':
        kelas = get_object_or_404(Kelas, id=kelas_id)
        nama_kelas = request.POST.get('nama_kelas')
        wali_kelas_id = request.POST.get('wali_kelas')

        if nama_kelas and wali_kelas_id:
            # Check if another class with the same name exists
            if Kelas.objects.filter(nama=nama_kelas).exclude(id=kelas_id).exists():
                messages.error(request, f"Kelas dengan nama '{nama_kelas}' sudah ada.")
            else:
                kelas.nama = nama_kelas
                kelas.wali_kelas_id = wali_kelas_id
                kelas.save()
                messages.success(request, f"Kelas '{nama_kelas}' berhasil diperbarui.")
        else:
            messages.error(request, "Nama kelas dan wali kelas harus diisi.")
            
    return redirect('data_siswa')


# ------------------------
# DATA GURU
# ------------------------
from django.shortcuts import render, redirect, get_object_or_404
from .models import Guru
from django.contrib import messages

def data_guru(request):
    if request.user.profile.role in ['guru', 'kepala'] and request.method == 'POST':
        messages.error(request, "Anda tidak memiliki akses untuk mengubah data guru.")
        return redirect('data_guru')

    # POST request untuk tambah atau edit
    if request.method == 'POST':
        edit_id = request.GET.get('edit_id')  # jika edit
        nip = request.POST.get('nip')
        if not nip:
            nip = None
        nama = request.POST.get('nama')
        jabatan = request.POST.get('jabatan')
        tempat_lahir = request.POST.get('tempat_lahir')
        tanggal_lahir = request.POST.get('tanggal_lahir')
        tanggal_masuk = request.POST.get('tanggal_masuk')
        alamat = request.POST.get('alamat')
        foto = request.FILES.get('foto')



        # Validasi NIP duplikat di server
        is_duplicate = Guru.objects.filter(nip=nip).exclude(pk=edit_id).exists()
        if nip and is_duplicate:
            messages.error(request, f"NIP {nip} sudah digunakan.")
            return redirect('data_guru')

        if edit_id:
            guru = get_object_or_404(Guru, pk=edit_id)
            guru.nip = nip
            guru.nama = nama.title()
            guru.jabatan = jabatan
            guru.tempat_lahir = tempat_lahir
            guru.tanggal_lahir = tanggal_lahir
            guru.tanggal_masuk = tanggal_masuk
            guru.alamat = alamat
            if foto:
                guru.foto = foto
            guru.save()
            messages.success(request, f"Data guru '{guru.nama}' berhasil diperbarui.")
        else:
            guru = Guru.objects.create(
                nip=nip,
                nama=nama.title(),
                jabatan=jabatan,
                tempat_lahir=tempat_lahir,
                tanggal_lahir=tanggal_lahir,
                tanggal_masuk=tanggal_masuk,
                alamat=alamat,
                foto=foto if foto else None
            )
            messages.success(request, f"Guru '{guru.nama}' berhasil ditambahkan.")

        return redirect('data_guru')

    # GET request -> tampilkan semua guru dengan paginasi
    guru_list = Guru.objects.all().order_by('nama')
    paginator = Paginator(guru_list, 10)  # 10 guru per halaman

    page_number = request.GET.get('page')
    try:
        guru_page = paginator.page(page_number)
    except PageNotAnInteger:
        guru_page = paginator.page(1)
    except EmptyPage:
        guru_page = paginator.page(paginator.num_pages)

    # Ambil semua NIP yang ada untuk validasi di client-side
    existing_nips = list(Guru.objects.values_list('nip', flat=True).exclude(nip__isnull=True).exclude(nip__exact=''))
    
    context = {
        'guru_page': guru_page,
        'existing_nips_json': json.dumps(existing_nips),
        'jabatan_choices': Guru.JABATAN_CHOICES,
    }
    return render(request, 'data_guru.html', context)


def guru_delete(request, guru_id):
    if request.user.profile.role in ['guru', 'kepala']:
        messages.error(request, "Anda tidak memiliki akses untuk menghapus data guru.")
        return redirect('data_guru')
    guru = get_object_or_404(Guru, pk=guru_id)
    nama = guru.nama
    guru.delete()
    messages.success(request, f"Guru '{nama}' berhasil dihapus.")
    return redirect('data_guru')



# ===============================
# Laporan Perkembangan
# ===============================

# ------------------------
# Fungsi bantu
# ------------------------
def tahun_ajaran_berjalan():
    today = date.today()
    year = today.year
    month = today.month
    # Misal tahun ajaran mulai Juli
    if month >= 7:  # Juli - Desember
        return f'{year}/{year+1}'
    else:  # Januari - Juni
        return f'{year-1}/{year}'

def semester_berjalan():
    today = date.today()
    if today.month >= 7:  # Juli - Desember
        return '1'
    else:  # Januari - Juni
        return '2'


# ------------------------
# Halaman Laporan Perkembangan
# ------------------------
@login_required
def laporan_perkembangan(request):
    user = request.user
    role = getattr(user.profile, 'role', None)
    read_only = role == 'kepala'

    # ===== Get active school year =====
    active_ta = TahunAjaran.objects.filter(is_active=True).first()
    
    # ===== Get filters =====
    q = request.GET.get('q', '')
    tahun_ajaran_default = active_ta.nama if active_ta else tahun_ajaran_berjalan()
    tahun_ajaran = request.GET.get('tahun_ajaran', tahun_ajaran_default)
    
    semester_default = semester_berjalan()
    semester = request.GET.get('semester', semester_default)
    kelas_id = request.GET.get('kelas')

    # ===== Aspek Perkembangan for the SELECTED year =====
    selected_ta_obj = TahunAjaran.objects.filter(nama=tahun_ajaran).first()
    aspek_list = AspekPerkembangan.objects.filter(tahun_ajaran=selected_ta_obj) if selected_ta_obj else AspekPerkembangan.objects.none()
    is_current_ta_semester = (tahun_ajaran == tahun_ajaran_default and semester == semester_default)


    # ===== Initial QuerySets =====
    siswa_qs = Siswa.objects.all()
    kelas_terpilih = None
    
    # ===== Apply primary filters =====
    if tahun_ajaran:
        siswa_qs = siswa_qs.filter(tahun_ajaran=tahun_ajaran)
    if q:
        siswa_qs = siswa_qs.filter(Q(nama__icontains=q) | Q(nomor_induk__icontains=q))

    # ===== Dynamic Class List & Auto-selection =====
    if q and not request.GET.get('kelas'):
        kelas_ids = siswa_qs.values_list('kelas_id', flat=True).distinct()
        kelas_list = Kelas.objects.filter(id__in=kelas_ids)
        if kelas_list.count() == 1:
            single_class = kelas_list.first()
            if single_class:
                kelas_id = str(single_class.id)
    else:
        kelas_list = Kelas.objects.all().order_by('nama')

    # ===== Role-based filtering =====
    if role == 'guru':
        try:
            guru_instance = Guru.objects.get(user=user)
            kelas_terpilih = Kelas.objects.get(wali_kelas=guru_instance)
            siswa_qs = siswa_qs.filter(kelas=kelas_terpilih)
            kelas_id = kelas_terpilih.id
        except (Guru.DoesNotExist, Kelas.DoesNotExist, Kelas.MultipleObjectsReturned):
            messages.error(request, "Data guru atau kelas Anda tidak ditemukan.")
            siswa_qs = Siswa.objects.none()
    
    elif role in ['admin', 'kepala']:
        if kelas_id:
            siswa_qs = siswa_qs.filter(kelas_id=kelas_id)
        elif not q:
            siswa_qs = Siswa.objects.none()

    # ===== Finalize context variables =====
    if kelas_id:
        try:
            kelas_terpilih = Kelas.objects.get(id=int(kelas_id))
        except (Kelas.DoesNotExist, ValueError, TypeError):
            kelas_terpilih = None

    # ===== Pagination =====
    paginator = Paginator(siswa_qs.order_by('nama'), 4)
    page_number = request.GET.get('page')
    try:
        siswa_page = paginator.page(page_number)
    except PageNotAnInteger:
        siswa_page = paginator.page(1)
    except EmptyPage:
        siswa_page = paginator.page(paginator.num_pages)

    # ===== Attach report data to students =====
    all_aspek_count = aspek_list.count()
    for siswa in siswa_page:
        laporan_qs = LaporanPerkembangan.objects.filter(
            siswa=siswa,
            siswa__tahun_ajaran=tahun_ajaran,
            semester=semester
        ).order_by('tanggal')
        
        for laporan in laporan_qs:
            filled_aspek_count = laporan.aspek.filter(Q(deskripsi__isnull=False, deskripsi__gt='') | Q(foto__isnull=False, foto__gt='')).count()
            is_ready = filled_aspek_count >= all_aspek_count > 0
            laporan.status_display = f"Semester {laporan.semester} - {'Siap' if is_ready else 'Belum'}"
        
        siswa.laporan_list = laporan_qs

    context = {
        "siswa_page": siswa_page,
        "q": q,
        "tahun_ajaran": tahun_ajaran,
        "tahun_ajaran_list": Siswa.objects.values_list('tahun_ajaran', flat=True).distinct().order_by('-tahun_ajaran'),
        "semester": semester,
        "read_only": read_only,
        "all_aspek": aspek_list,
        "kelas_list": kelas_list,
        "kelas_id": kelas_id,
        "kelas_terpilih": kelas_terpilih,
        "is_current_ta_semester": is_current_ta_semester,
        "active_ta_exists": active_ta is not None,
    }

    return render(request, "laporan_perkembangan.html", context)



@login_required
def tambah_aspek_ajax(request):
    if request.method == 'POST':
        nama_aspek = request.POST.get('nama_aspek')
        tahun_ajaran_nama = request.POST.get('tahun_ajaran')
        deskripsi = request.POST.get('deskripsi', '')

        if not tahun_ajaran_nama:
            return JsonResponse({'status': 'error', 'message': 'Tahun ajaran harus dipilih.'}, status=400)

        try:
            selected_ta = TahunAjaran.objects.get(nama=tahun_ajaran_nama)
        except TahunAjaran.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Tahun ajaran yang dipilih tidak valid.'}, status=400)

        if nama_aspek:
            if AspekPerkembangan.objects.filter(nama_aspek__iexact=nama_aspek, tahun_ajaran=selected_ta).exists():
                return JsonResponse({'status': 'error', 'message': 'Aspek dengan nama ini sudah ada untuk tahun ajaran yang dipilih.'}, status=400)
            
            aspek = AspekPerkembangan.objects.create(nama_aspek=nama_aspek, deskripsi=deskripsi, tahun_ajaran=selected_ta)
            return JsonResponse({'status': 'success', 'aspek': {'id': aspek.id, 'nama_aspek': aspek.nama_aspek, 'deskripsi': aspek.deskripsi}})
            
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)


@login_required
def laporan_tambah(request, siswa_id):
    siswa = get_object_or_404(Siswa, id=siswa_id)
    semester = request.GET.get('semester', semester_berjalan())
    
    if request.method == 'POST':
        laporan = LaporanPerkembangan.objects.create(
            siswa=siswa,
            semester=semester,
            status='belum'
        )

        # Ambil semua ID aspek yang dikirim dari form
        aspek_ids = [key.split('_')[1] for key in request.POST if key.startswith('deskripsi_')]

        for aspek_id in aspek_ids:
            aspek = get_object_or_404(AspekPerkembangan, id=aspek_id)
            deskripsi = request.POST.get(f'deskripsi_{aspek_id}', '')
            foto = request.FILES.get(f'foto_{aspek_id}')
            
            if deskripsi or foto:
                LaporanAspek.objects.create(
                    laporan=laporan,
                    aspek=aspek,
                    deskripsi=deskripsi,
                    foto=foto
                )

        messages.success(request, "Laporan berhasil ditambahkan!")
        return redirect('laporan_perkembangan')

    # Untuk GET request
    try:
        tahun_ajaran_obj = TahunAjaran.objects.get(nama=siswa.tahun_ajaran)
        aspek_list = AspekPerkembangan.objects.filter(tahun_ajaran=tahun_ajaran_obj)
    except TahunAjaran.DoesNotExist:
        aspek_list = AspekPerkembangan.objects.none()

    context = {
        'siswa': siswa,
        'aspek_list': aspek_list,
        'laporan': None,
        'semester': semester,
    }
    return render(request, 'laporan_form.html', context)

@login_required
def laporan_edit(request, pk):
    if request.user.profile.role == 'kepala':
        messages.error(request, "Anda tidak memiliki akses!")
        return redirect('laporan_perkembangan')

    laporan = get_object_or_404(LaporanPerkembangan, pk=pk)
    
    if request.method == 'POST':
        # Ambil semua ID aspek yang dikirim dari form
        aspek_ids = [key.split('_')[1] for key in request.POST if key.startswith('deskripsi_')]
        
        for aspek_id in aspek_ids:
            aspek = get_object_or_404(AspekPerkembangan, id=aspek_id)
            deskripsi = request.POST.get(f'deskripsi_{aspek_id}', '')
            foto = request.FILES.get(f'foto_{aspek_id}')

            laporan_aspek_obj, created = LaporanAspek.objects.get_or_create(
                laporan=laporan,
                aspek=aspek
            )

            laporan_aspek_obj.deskripsi = deskripsi
            if foto:
                laporan_aspek_obj.foto = foto
            
            if not deskripsi and not foto and not laporan_aspek_obj.foto:
                laporan_aspek_obj.delete()
            else:
                laporan_aspek_obj.save()

        messages.success(request, "Laporan berhasil diperbarui!")
        return redirect('laporan_perkembangan')

    # Untuk GET request
    try:
        tahun_ajaran_obj = TahunAjaran.objects.get(nama=laporan.siswa.tahun_ajaran)
        all_aspek = AspekPerkembangan.objects.filter(tahun_ajaran=tahun_ajaran_obj)
    except TahunAjaran.DoesNotExist:
        all_aspek = AspekPerkembangan.objects.none()

    existing_aspek_data = {la.aspek.id: la for la in laporan.aspek.all()}
    aspek_form_list = []
    for aspek in all_aspek:
        aspek_data = existing_aspek_data.get(aspek.id, 
            LaporanAspek(laporan=laporan, aspek=aspek, deskripsi='', foto=None)
        )
        aspek_form_list.append(aspek_data)

    context = {
        'laporan': laporan,
        'siswa': laporan.siswa,
        'aspek_list': aspek_form_list,
    }
    return render(request, 'laporan_form.html', context)


@login_required
def laporan_hapus(request, pk):
    if request.user.profile.role == 'kepala':
        messages.error(request, "Anda tidak memiliki akses!")
        return redirect('laporan_perkembangan')

    laporan = get_object_or_404(LaporanPerkembangan, pk=pk)
    laporan.delete()
    messages.success(request, "Laporan perkembangan berhasil dihapus!")
    return redirect('laporan_perkembangan')


# ABSENSI
@login_required
def absensi(request):
    user = request.user
    role = request.user.profile.role
    today = date.today()

    # ===== Get filters =====
    q = request.GET.get('q', '')
    tahun_ajaran = request.GET.get('tahun_ajaran', tahun_ajaran_berjalan())
    jenis_kelamin = request.GET.get('jenis_kelamin', '')
    kelas_id = request.GET.get('kelas')
    
    # ===== Initial QuerySets =====
    siswa_qs = Siswa.objects.all()
    kelas_terpilih = None

    # ===== Apply primary filters =====
    if tahun_ajaran:
        siswa_qs = siswa_qs.filter(tahun_ajaran=tahun_ajaran)
    if jenis_kelamin:
        siswa_qs = siswa_qs.filter(jenis_kelamin=jenis_kelamin)
    if q:
        siswa_qs = siswa_qs.filter(Q(nama__icontains=q) | Q(nomor_induk__icontains=q))

    # ===== Dynamic Class List & Auto-selection =====
    if q and not request.GET.get('kelas'):
        kelas_ids = siswa_qs.values_list('kelas_id', flat=True).distinct()
        kelas_list = Kelas.objects.filter(id__in=kelas_ids)
        if kelas_list.count() == 1:
            single_class = kelas_list.first()
            if single_class:
                kelas_id = str(single_class.id)
    else:
        kelas_list = Kelas.objects.all().order_by('nama')

    # ===== Role-based filtering =====
    if role == 'guru':
        try:
            guru_instance = Guru.objects.get(user=user)
            kelas_terpilih = Kelas.objects.get(wali_kelas=guru_instance)
            siswa_qs = siswa_qs.filter(kelas=kelas_terpilih) # Apply teacher's class filter
            kelas_id = kelas_terpilih.id
        except (Guru.DoesNotExist, Kelas.DoesNotExist, Kelas.MultipleObjectsReturned):
            messages.error(request, "Data guru atau kelas Anda tidak ditemukan.")
            siswa_qs = Siswa.objects.none()
    
    # ===== Role-based filtering =====
    if role == 'guru':
        try:
            guru_instance = Guru.objects.get(user=user)
            kelas_terpilih = Kelas.objects.get(wali_kelas=guru_instance)
            siswa_qs = siswa_qs.filter(kelas=kelas_terpilih) # Apply teacher's class filter
            kelas_id = kelas_terpilih.id
        except (Guru.DoesNotExist, Kelas.DoesNotExist, Kelas.MultipleObjectsReturned):
            messages.error(request, "Data guru atau kelas Anda tidak ditemukan.")
            siswa_qs = Siswa.objects.none()
    
    elif role == 'admin': # Only admin should filter by kelas_id or show none if no search
        if kelas_id:
            siswa_qs = siswa_qs.filter(kelas_id=kelas_id)
        elif not q:
            siswa_qs = Siswa.objects.none()

    # For 'kepala' role, siswa_qs should not be filtered by class here, and should show all students by default
    # The initial siswa_qs already applies tahun_ajaran, jenis_kelamin, and q filters.

    # ===== Finalize context variables =====
    if kelas_id:
        try:
            kelas_terpilih = Kelas.objects.get(id=int(kelas_id))
        except (Kelas.DoesNotExist, ValueError, TypeError):
            kelas_terpilih = None

    # ----------------- Pagination -----------------
    paginator = Paginator(siswa_qs.order_by('nama'), 10)
    page_number = request.GET.get('page')
    try:
        siswa_page = paginator.page(page_number)
    except PageNotAnInteger:
        siswa_page = paginator.page(1)
    except EmptyPage:
        siswa_page = paginator.page(paginator.num_pages)

    # ----------------- GURU (Daily Attendance) -----------------
    if role == 'guru':
        absensi_today_qs = Absensi.objects.filter(
            tanggal=today, 
            siswa__in=siswa_page.object_list
        )
        absensi_map = {absen.siswa_id: absen.get_status_display() for absen in absensi_today_qs}

        for siswa in siswa_page:
            siswa.absensi_hari_ini = absensi_map.get(siswa.id)

        all_absent = len(absensi_map) >= len(siswa_page.object_list) if siswa_page.object_list else False

        if request.method == "POST":
            if not all_absent:
                for siswa in siswa_page:
                    if siswa.id not in absensi_map:
                        status = request.POST.get(f'status_{siswa.id}')
                        if status:
                            Absensi.objects.update_or_create(
                                siswa=siswa,
                                tanggal=today,
                                defaults={'status': status}
                            )
                messages.success(request, "Absensi hari ini berhasil disimpan!")
            else:
                messages.warning(request, "Semua absensi untuk hari ini sudah tersimpan.")
            
            return redirect(request.get_full_path())

        context = {
            'role': role,
            'today': today,
            'siswa_page': siswa_page,
            'all_absent': all_absent,
            'tahun_ajaran_list': Siswa.objects.values_list('tahun_ajaran', flat=True).distinct().order_by('-tahun_ajaran'),
            'tahun_ajaran': tahun_ajaran,
            'jenis_kelamin': jenis_kelamin,
            'kelas_terpilih': kelas_terpilih,
            'q': q,
        }
        return render(request, 'absensi.html', context)

    # ----------------- ADMIN (Monthly Rekap) -----------------
    elif role == 'admin':
        bulan_get = request.GET.get('bulan', today.strftime('%Y-%m'))
        try:
            tahun, bulan = map(int, bulan_get.split('-'))
        except (ValueError, TypeError):
            tahun, bulan = today.year, today.month
            bulan_get = today.strftime('%Y-%m')

        _, days_in_month = monthrange(tahun, bulan)
        tanggal_list = [date(tahun, bulan, day) for day in range(1, days_in_month + 1)]

        siswa_data = []
        if kelas_id or q: # Only process if a class is selected or a search is made
            for siswa in siswa_page:
                status_harian = []
                for tgl in tanggal_list:
                    absensi_obj = Absensi.objects.filter(siswa=siswa, tanggal=tgl).first()
                    status_harian.append(absensi_obj.status if absensi_obj else "")
                siswa_data.append({'siswa': siswa, 'status_harian': status_harian})

        if request.method == "POST":
            for siswa in siswa_page:
                for i, tgl in enumerate(tanggal_list):
                    post_key = f'status_{siswa.id}_{i+1}'
                    if post_key in request.POST:
                        status = request.POST.get(post_key)
                        if not status:
                            Absensi.objects.filter(siswa=siswa, tanggal=tgl).delete()
                        else:
                            Absensi.objects.update_or_create(
                                siswa=siswa,
                                tanggal=tgl,
                                defaults={'status': status}
                            )
            messages.success(request, "Absensi berhasil diperbarui!")
            return redirect(request.get_full_path())

        context = {
            'role': role,
            'today': today,
            'siswa_data': siswa_data,
            'siswa_page': siswa_page,
            'tanggal_list': tanggal_list,
            'tahun_ajaran_list': Siswa.objects.values_list('tahun_ajaran', flat=True).distinct().order_by('-tahun_ajaran'),
            'tahun_ajaran': tahun_ajaran,
            'bulan': bulan_get,
            'jenis_kelamin': jenis_kelamin,
            'kelas_list': kelas_list,
            'kelas_id': kelas_id,
            'kelas_terpilih': kelas_terpilih,
            'q': q,
        }
        return render(request, 'absensi.html', context)

    # ----------------- KEPALA (Stats) -----------------
    elif role == 'kepala':
        bulan_get = request.GET.get('bulan', today.strftime('%Y-%m'))
        try:
            tahun, bulan = map(int, bulan_get.split('-'))
        except (ValueError, TypeError):
            tahun, bulan = today.year, today.month
            bulan_get = today.strftime('%Y-%m')

        statuses = ['Hadir', 'Sakit', 'Izin', 'Alpa']
        
        # For 'kepala' role, stats should be for all students (siswa_qs is already filtered by TA, JK, Q)
        # No class filter should be applied here.

        stats_harian = {
            st: Absensi.objects.filter(
                tanggal=today,
                status=st,
                siswa__in=siswa_qs
            ).count() for st in statuses
        }

        _, days_in_month = monthrange(tahun, bulan)
        tanggal_list_full = [date(tahun, bulan, day) for day in range(1, days_in_month + 1)]
        
        effective_days_count = 0
        for d in tanggal_list_full:
            if d.weekday() < 5: # Monday=0 to Friday=4
                effective_days_count += 1

        # Calculate total rekap for the month, considering only effective days
        rekap_bulanan = {'Hadir':0, 'Sakit':0, 'Izin':0, 'Alpa':0}
        for siswa in siswa_qs:
            for d in tanggal_list_full:
                if d.weekday() < 5: # Only count for weekdays
                    absensi_obj = Absensi.objects.filter(siswa=siswa, tanggal=d).first()
                    if absensi_obj and absensi_obj.status in rekap_bulanan:
                        rekap_bulanan[absensi_obj.status] += 1
        
        total_effective_records = len(siswa_qs) * effective_days_count
        persentase_hadir = (rekap_bulanan['Hadir'] / total_effective_records * 100) if total_effective_records > 0 else 0
        persentase_sakit = (rekap_bulanan['Sakit'] / total_effective_records * 100) if total_effective_records > 0 else 0
        persentase_izin = (rekap_bulanan['Izin'] / total_effective_records * 100) if total_effective_records > 0 else 0
        persentase_alpa = (rekap_bulanan['Alpa'] / total_effective_records * 100) if total_effective_records > 0 else 0

        absensi_bulanan = OrderedDict()
        for tgl in tanggal_list_full:
            stats = {st: Absensi.objects.filter(
                        tanggal=tgl,
                        status=st,
                        siswa__in=siswa_qs
                     ).count() for st in statuses}
            absensi_bulanan[tgl.strftime('%d-%m-%Y')] = stats

        context = {
            'role': role,
            'today': today,
            'stats_harian': stats_harian,
            'absensi_bulanan': absensi_bulanan,
            'siswa_page': siswa_page, # This is still paginated, but based on unfiltered siswa_qs (by class)
            'bulan': bulan_get,
            'jenis_kelamin': jenis_kelamin,
            'tahun_ajaran_list': Siswa.objects.values_list('tahun_ajaran', flat=True).distinct().order_by('-tahun_ajaran'),
            'tahun_ajaran': tahun_ajaran,
            'kelas_list': Kelas.objects.all().order_by('nama'), # Show all classes in dropdown for kepala
            'kelas_id': kelas_id, # Keep for selected value in dropdown
            'kelas_terpilih': kelas_terpilih, # Keep for display if selected
            'q': q,
            'persentase_hadir': persentase_hadir,
            'persentase_sakit': persentase_sakit,
            'persentase_izin': persentase_izin,
            'persentase_alpa': persentase_alpa,
        }
        return render(request, 'absensi.html', context)

@login_required
def absensi_submit(request):
    if request.method == 'POST':
        today = date.today()
        siswa_list = Siswa.objects.filter(tahun_ajaran=tahun_ajaran_berjalan())
        for siswa in siswa_list:
            status = request.POST.get(f'status_{siswa.id}')
            if status:
                Absensi.objects.update_or_create(
                    siswa=siswa,
                    tanggal=today,
                    defaults={'status': status}
                )
        messages.success(request, "Absensi hari ini berhasil disimpan!")
    return redirect('absensi')


@login_required
def absensi_download_pdf(request):
    if request.user.profile.role != 'admin':
        messages.error(request, "Anda tidak memiliki akses!")
        return redirect('absensi')

    # Ambil filter dari query string
    tahun_ajaran = request.GET.get('tahun_ajaran', tahun_ajaran_berjalan())
    bulan_get = request.GET.get('bulan', date.today().strftime('%Y-%m'))
    jenis_kelamin = request.GET.get('jenis_kelamin', '')
    kelas_id = request.GET.get('kelas')

    tahun, bulan = map(int, bulan_get.split('-'))
    bulan_nama = datetime(tahun, bulan, 1).strftime("%B %Y")
    _, days_in_month = monthrange(tahun, bulan)
    tanggal_list = [day for day in range(1, days_in_month+1)]

    tanggal_info = []
    effective_days_count = 0
    for day in tanggal_list:
        current_date = date(tahun, bulan, day)
        is_weekend = current_date.weekday() >= 5 # Saturday is 5, Sunday is 6
        tanggal_info.append({'day': day, 'is_weekend': is_weekend})
        if not is_weekend:
            effective_days_count += 1

    # Ambil data siswa sesuai filter
    siswa_qs = Siswa.objects.filter(tahun_ajaran=tahun_ajaran)
    if jenis_kelamin:
        siswa_qs = siswa_qs.filter(jenis_kelamin=jenis_kelamin)
    if kelas_id and kelas_id != 'None': # Tambahkan filter kelas
        siswa_qs = siswa_qs.filter(kelas_id=kelas_id)

    kelas_terpilih = None
    if kelas_id and kelas_id != 'None':
        try:
            kelas_terpilih = Kelas.objects.get(id=int(kelas_id))
        except (Kelas.DoesNotExist, ValueError):
            pass

    siswa_data = []
    for siswa in siswa_qs:
        daily_status_info = []
        for day_info in tanggal_info:
            tgl = date(tahun, bulan, day_info['day'])
            absensi_obj = Absensi.objects.filter(siswa=siswa, tanggal=tgl).first()
            daily_status_info.append({
                'status': absensi_obj.status if absensi_obj else "",
                'is_weekend': day_info['is_weekend']
            })
        siswa_data.append({'siswa': siswa, 'daily_status_info': daily_status_info})

    # Rekap H, S, I, A (hanya hari efektif)
    rekap = {'Hadir':0, 'Sakit':0, 'Izin':0, 'Alpa':0}
    for row in siswa_data:
        for day_status in row['daily_status_info']:
            if not day_status['is_weekend']:
                status = day_status['status']
                if status in rekap:
                    rekap[status] += 1
    
    # Hitung persentase (berdasarkan hari efektif)
    total_effective_records = len(siswa_qs) * effective_days_count
    persentase_sakit = (rekap['Sakit'] / total_effective_records * 100) if total_effective_records > 0 else 0
    persentase_izin = (rekap['Izin'] / total_effective_records * 100) if total_effective_records > 0 else 0
    persentase_alpa = (rekap['Alpa'] / total_effective_records * 100) if total_effective_records > 0 else 0

    # Ambil data guru
    wali_kelas = None
    if kelas_terpilih and kelas_terpilih.wali_kelas:
        wali_kelas = kelas_terpilih.wali_kelas
    kepala_sekolah = Guru.objects.filter(jabatan='kepala_sekolah').first()

    context = {
        'judul': 'Absensi Siswa TK Negeri 7 Tanjungpinang',
        'bulan_nama': bulan_nama,
        'siswa_data': siswa_data,
        'tanggal_info': tanggal_info,
        'rekap': rekap,
        'wali_kelas': wali_kelas,
        'kepala_sekolah': kepala_sekolah,
        'kelas_terpilih': kelas_terpilih,
        'persentase_sakit': persentase_sakit,
        'persentase_izin': persentase_izin,
        'persentase_alpa': persentase_alpa,
    }

    # Render template menjadi PDF
    html_string = render_to_string('absensi_pdf.html', context, request=request)
    html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Absensi_{bulan_nama}.pdf"'
    
    html.write_pdf(response)
    return response


#============RAPORT DIGITAL=============
@login_required
def raport_digital(request):
    user = request.user
    role = getattr(user.profile, 'role', None)
    read_only = role == 'kepala'

    # ===== Get filters =====
    q = request.GET.get('q', '').strip()
    tahun_ajaran_default = tahun_ajaran_berjalan()
    tahun_ajaran = request.GET.get('tahun_ajaran', tahun_ajaran_default)
    semester_default = semester_berjalan()
    semester = request.GET.get('semester', semester_default)
    jenis_kelamin = request.GET.get('jenis_kelamin', '')
    kelas_id = request.GET.get('kelas')

    # ===== Initial QuerySets =====
    siswa_qs = Siswa.objects.all()
    kelas_terpilih = None

    # ===== Apply primary filters =====
    if tahun_ajaran:
        siswa_qs = siswa_qs.filter(tahun_ajaran=tahun_ajaran)
    if jenis_kelamin:
        siswa_qs = siswa_qs.filter(jenis_kelamin=jenis_kelamin)
    if q:
        siswa_qs = siswa_qs.filter(
            Q(nama__icontains=q) |
            Q(nisn__icontains=q) |
            Q(nomor_induk__icontains=q)
        )

    # ===== Dynamic Class List & Auto-selection =====
    if q and not request.GET.get('kelas'):
        kelas_ids = siswa_qs.values_list('kelas_id', flat=True).distinct()
        kelas_list = Kelas.objects.filter(id__in=kelas_ids)
        if kelas_list.count() == 1:
            single_class = kelas_list.first()
            if single_class:
                kelas_id = str(single_class.id)
    else:
        kelas_list = Kelas.objects.all().order_by('nama')

    # ===== Role-based filtering =====
    if role == 'guru':
        try:
            guru_instance = Guru.objects.get(user=user)
            kelas_terpilih = Kelas.objects.get(wali_kelas=guru_instance)
            siswa_qs = siswa_qs.filter(kelas=kelas_terpilih) # Apply teacher's class filter
            kelas_id = kelas_terpilih.id
        except (Guru.DoesNotExist, Kelas.DoesNotExist, Kelas.MultipleObjectsReturned):
            messages.error(request, "Data guru atau kelas Anda tidak ditemukan.")
            siswa_qs = Siswa.objects.none()
    
    elif role in ['admin', 'kepala']:
        if kelas_id:
            siswa_qs = siswa_qs.filter(kelas_id=kelas_id)
        elif not q: # If not searching, admin/kepala must select a class
            siswa_qs = Siswa.objects.none()

    # ===== Finalize context variables =====
    if kelas_id:
        try:
            kelas_terpilih = Kelas.objects.get(id=int(kelas_id))
        except (Kelas.DoesNotExist, ValueError, TypeError):
            kelas_terpilih = None

    # ===== Pagination =====
    paginator = Paginator(siswa_qs.order_by('nama'), 4)
    page_number = request.GET.get('page')
    try:
        siswa_page = paginator.page(page_number)
    except PageNotAnInteger:
        siswa_page = paginator.page(1)
    except EmptyPage:
        siswa_page = paginator.page(paginator.num_pages)

    # ===== Cek status rapor untuk setiap siswa di halaman ini =====
    selected_ta_obj = TahunAjaran.objects.filter(nama=tahun_ajaran).first()
    all_aspek_count = AspekPerkembangan.objects.filter(tahun_ajaran=selected_ta_obj).count() if selected_ta_obj else 0

    for siswa in siswa_page:
        laporan = LaporanPerkembangan.objects.filter(
            siswa=siswa,
            siswa__tahun_ajaran=tahun_ajaran,
            semester=str(semester)
        ).order_by('-tanggal').first()

        siswa.laporan_semester_ini = laporan  # Tetapkan objek laporan

        if not laporan:
            siswa.raport_status = 'tidak_ada'
        else:
            filled_aspek_count = laporan.aspek.filter(Q(deskripsi__isnull=False, deskripsi__gt='') | Q(foto__isnull=False, foto__gt='')).count()
            is_ready = filled_aspek_count >= all_aspek_count > 0
            siswa.raport_status = 'lengkap' if is_ready else 'belum_lengkap'

    # ===== Get Reflections for the selected year =====
    selected_ta_obj = TahunAjaran.objects.filter(nama=tahun_ajaran).first()
    all_refleksi = RefleksiKomentar.objects.filter(tahun_ajaran=selected_ta_obj) if selected_ta_obj else RefleksiKomentar.objects.none()

    context = {
        "siswa_page": siswa_page,
        "read_only": read_only,
        "tahun_ajaran_list": Siswa.objects.values_list('tahun_ajaran', flat=True).distinct().order_by('-tahun_ajaran'),
        "tahun_ajaran": tahun_ajaran,
        "semester": semester,
        "q": q,
        "jenis_kelamin": jenis_kelamin,
        "kelas_list": kelas_list,
        "kelas_id": kelas_id,
        "kelas_terpilih": kelas_terpilih,
        "all_refleksi": all_refleksi, # Add this to context
    }

    return render(request, "raport_digital.html", context)




@login_required
@require_http_methods(["GET", "POST", "DELETE"])
def manage_active_reflections_ajax(request, comment_id=None):
    if request.user.profile.role != 'admin':
        return JsonResponse({'success': False, 'error': 'Akses ditolak.'}, status=403)

    try:
        active_ta = TahunAjaran.objects.get(is_active=True)
    except TahunAjaran.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Tidak ada tahun ajaran aktif yang ditetapkan.'}, status=404)

    # Ambil semua komentar untuk tahun ajaran aktif
    if request.method == 'GET':
        comments = RefleksiKomentar.objects.filter(tahun_ajaran=active_ta).order_by('-created_at')
        return JsonResponse({'success': True, 'reflections': list(comments.values('id', 'teks'))})

    # Tambah atau Edit komentar
    elif request.method == 'POST':
        text = request.POST.get('text')
        if not text:
            return JsonResponse({'success': False, 'error': 'Teks tidak boleh kosong.'}, status=400)

        if comment_id: # Edit
            comment = get_object_or_404(RefleksiKomentar, id=comment_id, tahun_ajaran=active_ta)
            comment.teks = text
            comment.save()
            return JsonResponse({'success': True, 'reflection': {'id': comment.id, 'text': comment.teks}})
        else: # Tambah
            comment = RefleksiKomentar.objects.create(teks=text, tahun_ajaran=active_ta)
            return JsonResponse({'success': True, 'reflection': {'id': comment.id, 'text': comment.teks}})

    # Hapus komentar
    elif request.method == 'DELETE':
        if not comment_id:
            return JsonResponse({'success': False, 'error': 'ID komentar tidak disediakan.'}, status=400)
        comment = get_object_or_404(RefleksiKomentar, id=comment_id, tahun_ajaran=active_ta)
        comment.delete()
        return JsonResponse({'success': True})

    return JsonResponse({'success': False, 'error': 'Metode tidak valid.'}, status=405)


@login_required
def cetak_biodata(request, siswa_id):
    siswa = get_object_or_404(Siswa, id=siswa_id)
    
    # ambil guru yang jadi kepala sekolah
    kepala = Guru.objects.filter(jabatan="kepala_sekolah").first()
    
    context = {
        "siswa": siswa,
        "kepala": kepala,
    }
    return render(request, "cetak_biodata.html", context)


@login_required
def biodata_pdf(request, siswa_id):
    siswa = get_object_or_404(Siswa, id=siswa_id)
    kepala = Guru.objects.filter(jabatan="kepala_sekolah").first()

    # Buat URL lengkap foto
    foto_url = None
    if siswa.foto and hasattr(siswa.foto, 'url'):
        foto_url = request.build_absolute_uri(siswa.foto.url)

    context = {
        "siswa": siswa,
        "kepala": kepala,
        "foto_url": foto_url,  # kirim ke template
    }

    html_string = render_to_string('biodata_pdf.html', context, request=request)
    html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Biodata_{siswa.nama}.pdf"'

    html.write_pdf(response)
    return response


def cetak_raport(request, siswa_id):
    siswa = get_object_or_404(Siswa, id=siswa_id)
    
    # Ambil tahun ajaran dan semester dari URL
    tahun_ajaran_nama = request.GET.get('tahun_ajaran', siswa.tahun_ajaran)
    semester = request.GET.get('semester')

    # Jika semester tidak ada di URL, tentukan semester berjalan
    if not semester:
        today = date.today()
        if today.month >= 7:
            semester = '1'
        else:
            semester = '2'

    # Ambil laporan siswa untuk semester dan tahun ajaran yang sesuai
    laporan = LaporanPerkembangan.objects.filter(
        siswa=siswa,
        semester=semester,
        siswa__tahun_ajaran=tahun_ajaran_nama
    ).order_by('-tanggal').first()

    # --- NEW LOGIC ---
    aspek_list_for_template = []
    if laporan:
        try:
            # Get all possible aspects for that academic year
            tahun_ajaran_obj = TahunAjaran.objects.get(nama=laporan.siswa.tahun_ajaran)
            all_aspek_for_year = AspekPerkembangan.objects.filter(tahun_ajaran=tahun_ajaran_obj)

            # Get existing data from the report
            existing_aspek_data = {la.aspek.id: la for la in laporan.aspek.all()}

            # Build the list for the template
            for aspek_template in all_aspek_for_year:
                # Get the saved data or create an empty placeholder in memory
                aspek_data = existing_aspek_data.get(aspek_template.id, None)

                if aspek_data is None:
                    # Create a placeholder LaporanAspek object in memory
                    # This object needs to mimic the structure of a real LaporanAspek
                    # so that the template can access aspek.nama_aspek, aspek.deskripsi, aspek.foto
                    class PlaceholderLaporanAspek:
                        def __init__(self, aspek_template):
                            self.aspek = aspek_template
                            self.deskripsi = "" # Default empty description
                            self.foto = None    # Default no photo

                    aspek_data = PlaceholderLaporanAspek(aspek_template)

                # --- DI SINI KITA AKAN MENAMBAHKAN LOGIKA DIMENSI GAMBAR ---
                if aspek_data.foto and hasattr(aspek_data.foto, 'width') and hasattr(aspek_data.foto, 'height'):
                    if aspek_data.foto.width > aspek_data.foto.height:
                        aspek_data.orientation = 'landscape'
                        aspek_data.display_width = '450px'
                        aspek_data.display_height = '300px'
                    elif aspek_data.foto.height > aspek_data.foto.width:
                        aspek_data.orientation = 'portrait'
                        aspek_data.display_width = '300px'
                        aspek_data.display_height = '450px'
                    else:
                        aspek_data.orientation = 'square'
                        aspek_data.display_width = '360px'
                        aspek_data.display_height = '360px'
                else:
                    aspek_data.orientation = 'none'
                    aspek_data.display_width = 'auto'
                    aspek_data.display_height = 'auto'
                # --- AKHIR LOGIKA DIMENSI GAMBAR ---
                aspek_list_for_template.append(aspek_data)

        except TahunAjaran.DoesNotExist:
            # If TA doesn't exist, do nothing, list will be empty
            pass
    # --- END NEW LOGIC ---

    # --- NEW/CORRECT logic for reflections ---
    refleksi_list = []
    try:
        tahun_ajaran_obj = TahunAjaran.objects.get(nama=tahun_ajaran_nama)
        refleksi_list = RefleksiKomentar.objects.filter(tahun_ajaran=tahun_ajaran_obj)
    except TahunAjaran.DoesNotExist:
        pass # refleksi_list will be empty

    # Hitung kehadiran semester
    try:
        year_str = tahun_ajaran_nama.split('/')[0]
        year = int(year_str)
        
        if semester == '1':
            start = date(year, 7, 1)
            end = date(year, 12, 31)
        else:
            start = date(year + 1, 1, 1)
            end = date(year + 1, 6, 30)

        absensi_semester = Absensi.objects.filter(
            siswa=siswa,
            tanggal__range=(start, end)
        )
        total_sakit = absensi_semester.filter(status='Sakit').count()
        total_izin = absensi_semester.filter(status='Izin').count()
        total_alpha = absensi_semester.filter(status='Alpa').count()
    except (ValueError, IndexError, TypeError):
        total_sakit = 0
        total_izin = 0
        total_alpha = 0
    # Ambil data kepala sekolah
    kepala_sekolah = Guru.objects.filter(jabatan='kepala_sekolah').first()
    
    # Ambil wali kelas dari kelas siswa yang bersangkutan
    wali_kelas = None
    kelas_nama = None
    if siswa.kelas:
        kelas_nama = siswa.kelas.nama
        if siswa.kelas.wali_kelas:
            wali_kelas = siswa.kelas.wali_kelas

    context = {
        'siswa': siswa,
        'laporan': laporan,
        'aspek_list': aspek_list_for_template,
        'semester': semester,
        'tahun_ajaran': tahun_ajaran_nama,
        'refleksi_list': refleksi_list,
        'total_sakit': total_sakit,
        'total_izin': total_izin,
        'total_alpha': total_alpha,
        'kepala_sekolah': kepala_sekolah,
        'wali_kelas': wali_kelas,
        'kelas_nama': kelas_nama,
    }
    return render(request, 'cetak_raport.html', context)


@login_required
def raport_pdf(request, laporan_id):
    # Start with laporan_id
    laporan = get_object_or_404(LaporanPerkembangan, pk=laporan_id)
    siswa = laporan.siswa
    
    # Get other params from request or object
    tahun_ajaran_nama = request.GET.get('tahun_ajaran', siswa.tahun_ajaran)
    semester = request.GET.get('semester', laporan.semester)

    # --- Copy logic from cetak_raport ---

    # 1. Aspect list logic
    aspek_list_for_template = []
    try:
        tahun_ajaran_obj = TahunAjaran.objects.get(nama=laporan.siswa.tahun_ajaran)
        all_aspek_for_year = AspekPerkembangan.objects.filter(tahun_ajaran=tahun_ajaran_obj)
        existing_aspek_data = {la.aspek.id: la for la in laporan.aspek.all()}
        for aspek_template in all_aspek_for_year:
            aspek_data = existing_aspek_data.get(aspek_template.id, 
                LaporanAspek(laporan=laporan, aspek=aspek_template, deskripsi='', foto=None)
            )
            if aspek_data.foto and hasattr(aspek_data.foto, 'width') and hasattr(aspek_data.foto, 'height'):
                if aspek_data.foto.width > aspek_data.foto.height:
                    aspek_data.orientation = 'landscape'
                    aspek_data.display_width = '300px'
                    aspek_data.display_height = '200px'
                elif aspek_data.foto.height > aspek_data.foto.width:
                    aspek_data.orientation = 'portrait'
                    aspek_data.display_width = '200px'
                    aspek_data.display_height = '300px'
                else:
                    aspek_data.orientation = 'square'
                    aspek_data.display_width = '240px'
                    aspek_data.display_height = '240px'
            else:
                aspek_data.orientation = 'none'
                aspek_data.display_width = 'auto'
                aspek_data.display_height = 'auto'
            aspek_list_for_template.append(aspek_data)
    except TahunAjaran.DoesNotExist:
        pass

    # 2. Reflection list logic
    refleksi_list = []
    try:
        tahun_ajaran_obj = TahunAjaran.objects.get(nama=tahun_ajaran_nama)
        refleksi_list = RefleksiKomentar.objects.filter(tahun_ajaran=tahun_ajaran_obj)
    except TahunAjaran.DoesNotExist:
        pass

    # 3. Attendance logic
    try:
        year_str = tahun_ajaran_nama.split('/')[0]
        year = int(year_str)
        if semester == '1':
            start = date(year, 7, 1)
            end = date(year, 12, 31)
        else:
            start = date(year + 1, 1, 1)
            end = date(year + 1, 6, 30)
        absensi_semester = Absensi.objects.filter(siswa=siswa, tanggal__range=(start, end))
        total_sakit = absensi_semester.filter(status='Sakit').count()
        total_izin = absensi_semester.filter(status='Izin').count()
        total_alpha = absensi_semester.filter(status='Alpa').count()
    except (ValueError, IndexError, TypeError):
        total_sakit, total_izin, total_alpha = 0, 0, 0

    # 4. Guru/Kepala Sekolah logic
    kepala_sekolah = Guru.objects.filter(jabatan='kepala_sekolah').first()
    wali_kelas = siswa.kelas.wali_kelas if siswa.kelas and siswa.kelas.wali_kelas else None
    kelas_nama = siswa.kelas.nama if siswa.kelas else None

    # 5. Build context
    context = {
        'siswa': siswa,
        'laporan': laporan,
        'aspek_list': aspek_list_for_template,
        'semester': semester,
        'tahun_ajaran': tahun_ajaran_nama,
        'refleksi_list': refleksi_list,
        'total_sakit': total_sakit,
        'total_izin': total_izin,
        'total_alpha': total_alpha,
        'kepala_sekolah': kepala_sekolah,
        'wali_kelas': wali_kelas,
        'kelas_nama': kelas_nama,
    }

    # 6. Render cetak_raport.html
    html_string = render_to_string('raport_pdf.html', context, request=request)
    html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Raport_{siswa.nama}.pdf"'
    
    html.write_pdf(response)
    return response


@login_required
def hapus_aspek_ajax(request, aspek_id):
    if request.method == 'POST':
        try:
            aspek = get_object_or_404(AspekPerkembangan, id=aspek_id)
            aspek.delete()
            return JsonResponse({'status': 'success', 'message': 'Aspek berhasil dihapus.'})
        except ProtectedError:
            return JsonResponse({'status': 'error', 'message': 'Aspek ini tidak bisa dihapus karena sedang digunakan dalam laporan siswa.'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
            
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)


@login_required
def manage_users(request):
    if request.user.profile.role != 'admin':
        messages.error(request, "Anda tidak memiliki akses ke halaman ini.")
        return redirect('admin_dashboard') # Atau halaman lain yang sesuai

    users = User.objects.all().order_by('username')
    gurus_without_user = Guru.objects.filter(user__isnull=True)

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.save()

            guru_id = request.POST.get('guru_id')
            if guru_id:
                guru = get_object_or_404(Guru, id=guru_id)
                guru.user = user
                guru.save()
                Profile.objects.update_or_create(user=user, defaults={'role': 'guru'})
                messages.success(request, f"User '{user.username}' berhasil dibuat dan dikaitkan dengan guru {guru.nama}.")
            else:
                # Jika tidak ada guru yang dipilih, secara default buat profile dengan role 'guru'
                Profile.objects.update_or_create(user=user, defaults={'role': 'guru'})
                messages.success(request, f"User '{user.username}' berhasil dibuat.")
            
            return redirect('manage_users')
        else:
            messages.error(request, "Terjadi kesalahan saat membuat user baru.")
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = UserCreationForm()

    context = {
        'users': users,
        'gurus_without_user': gurus_without_user,
        'form': form,
    }
    return render(request, 'manage_users.html', context)


@login_required
def create_user_for_guru(request, guru_id):
    if request.user.profile.role != 'admin':
        messages.error(request, "Anda tidak memiliki akses ke halaman ini.")
        return redirect('admin_dashboard')

    guru = get_object_or_404(Guru, id=guru_id)

    # Cek apakah guru sudah memiliki user
    if hasattr(guru, 'user') and guru.user:
        messages.warning(request, f"Guru {guru.nama} sudah memiliki akun user.")
        return redirect('manage_users')

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.save()
            # Kaitkan user dengan guru
            guru.user = user
            guru.save()
            # Buat atau update Profile dengan role 'guru'
            Profile.objects.update_or_create(user=user, defaults={'role': 'guru'})
            messages.success(request, f"Akun user '{user.username}' berhasil dibuat untuk guru {guru.nama}.")
            return redirect('manage_users')
        else:
            messages.error(request, "Terjadi kesalahan saat membuat user baru.")
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        # Saran username dari nama guru
        suggested_username = guru.nama.lower().replace(' ', '.')
        form = UserCreationForm(initial={'username': suggested_username})

    context = {
        'form': form,
        'guru': guru,
    }
    return render(request, 'create_user_for_guru.html', context)


@login_required
def user_edit(request, user_id):
    if request.user.profile.role != 'admin':
        messages.error(request, "Anda tidak memiliki akses ke halaman ini.")
        return redirect('admin_dashboard')

    user_to_edit = get_object_or_404(User, id=user_id)
    profile_to_edit = get_object_or_404(Profile, user=user_to_edit)

    if request.method == 'POST':
        form = UserChangeForm(request.POST, instance=user_to_edit)
        
        new_role = request.POST.get('role')
        if new_role and new_role in [choice[0] for choice in Profile.ROLE_CHOICES]:
            profile_to_edit.role = new_role
            profile_to_edit.save()
        
        if form.is_valid():
            form.save()
            messages.success(request, f"User '{user_to_edit.username}' berhasil diperbarui.")
            return redirect('manage_users')
        else:
            messages.error(request, "Terjadi kesalahan saat memperbarui user.")
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = UserChangeForm(instance=user_to_edit)
    
    context = {
        'form': form,
        'user_to_edit': user_to_edit,
        'profile_to_edit': profile_to_edit,
        'role_choices': Profile.ROLE_CHOICES,
    }
    return render(request, 'user_edit.html', context)


@login_required
def user_delete(request, user_id):
    if request.user.profile.role != 'admin':
        messages.error(request, "Anda tidak memiliki akses ke halaman ini.")
        return redirect('admin_dashboard')

    user_to_delete = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        if user_to_delete == request.user:
            messages.error(request, "Anda tidak dapat menghapus akun Anda sendiri.")
            return redirect('manage_users')
        
        username = user_to_delete.username
        user_to_delete.delete()
        messages.success(request, f"User '{username}' berhasil dihapus.")
        return redirect('manage_users')
@login_required
def edit_aspek_ajax(request, aspek_id):
    if request.method == 'POST':
        try:
            aspek = get_object_or_404(AspekPerkembangan, id=aspek_id)
            
            new_nama = request.POST.get('nama_aspek')
            new_deskripsi = request.POST.get('deskripsi', '')
            tahun_ajaran_nama = request.POST.get('tahun_ajaran')

            if not new_nama:
                return JsonResponse({'status': 'error', 'message': 'Nama aspek tidak boleh kosong.'}, status=400)
            if not tahun_ajaran_nama:
                return JsonResponse({'status': 'error', 'message': 'Tahun ajaran harus dipilih.'}, status=400)

            try:
                selected_ta = TahunAjaran.objects.get(nama=tahun_ajaran_nama)
            except TahunAjaran.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Tahun ajaran yang dipilih tidak valid.'}, status=400)

            # Check for duplicates in the selected school year
            if AspekPerkembangan.objects.filter(nama_aspek__iexact=new_nama, tahun_ajaran=selected_ta).exclude(id=aspek_id).exists():
                return JsonResponse({'status': 'error', 'message': 'Aspek dengan nama ini sudah ada untuk tahun ajaran yang dipilih.'}, status=400)

            aspek.nama_aspek = new_nama
            aspek.deskripsi = new_deskripsi
            # Note: We don't change the tahun_ajaran of an existing aspect upon edit.
            aspek.save()
            return JsonResponse({'status': 'success', 'aspek': {'id': aspek.id, 'nama_aspek': aspek.nama_aspek, 'deskripsi': aspek.deskripsi}})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
            
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def tambah_refleksi_ajax(request):
    if request.user.profile.role != 'admin':
        return JsonResponse({'status': 'error', 'message': 'Akses ditolak.'}, status=403)
    if request.method == 'POST':
        teks = request.POST.get('teks')
        tahun_ajaran_nama = request.POST.get('tahun_ajaran')

        if not teks or not tahun_ajaran_nama:
            return JsonResponse({'status': 'error', 'message': 'Data tidak lengkap.'}, status=400)

        try:
            selected_ta = TahunAjaran.objects.get(nama=tahun_ajaran_nama)
        except TahunAjaran.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Tahun ajaran yang dipilih tidak valid.'}, status=400)

        if RefleksiKomentar.objects.filter(teks__iexact=teks, tahun_ajaran=selected_ta).exists():
            return JsonResponse({'status': 'error', 'message': 'Refleksi ini sudah ada untuk tahun ajaran yang dipilih.'}, status=400)
        
        refleksi = RefleksiKomentar.objects.create(teks=teks, tahun_ajaran=selected_ta)
        return JsonResponse({'status': 'success', 'refleksi': {'id': refleksi.id, 'teks': refleksi.teks}})
            
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

@login_required
def edit_refleksi_ajax(request, refleksi_id):
    if request.user.profile.role != 'admin':
        return JsonResponse({'status': 'error', 'message': 'Akses ditolak.'}, status=403)
    if request.method == 'POST':
        try:
            refleksi = get_object_or_404(RefleksiKomentar, id=refleksi_id)
            
            new_teks = request.POST.get('teks')
            tahun_ajaran_nama = request.POST.get('tahun_ajaran')

            if not new_teks or not tahun_ajaran_nama:
                return JsonResponse({'status': 'error', 'message': 'Data tidak lengkap.'}, status=400)

            try:
                selected_ta = TahunAjaran.objects.get(nama=tahun_ajaran_nama)
            except TahunAjaran.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Tahun ajaran yang dipilih tidak valid.'}, status=400)

            if RefleksiKomentar.objects.filter(teks__iexact=new_teks, tahun_ajaran=selected_ta).exclude(id=refleksi_id).exists():
                return JsonResponse({'status': 'error', 'message': 'Refleksi ini sudah ada untuk tahun ajaran yang dipilih.'}, status=400)

            refleksi.teks = new_teks
            refleksi.save()
            return JsonResponse({'status': 'success', 'refleksi': {'id': refleksi.id, 'teks': refleksi.teks}})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
            
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def hapus_refleksi_ajax(request, refleksi_id):
    if request.user.profile.role != 'admin':
        return JsonResponse({'status': 'error', 'message': 'Akses ditolak.'}, status=403)
    if request.method == 'POST':
        try:
            refleksi = get_object_or_404(RefleksiKomentar, id=refleksi_id)
            refleksi.delete()
            return JsonResponse({'status': 'success', 'message': 'Refleksi berhasil dihapus.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
            
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

import pandas as pd

def download_siswa_excel(request):
    kelas_id = request.GET.get('kelas')
    
    siswa_list = Siswa.objects.all()
    
    if kelas_id:
        siswa_list = siswa_list.filter(kelas_id=kelas_id)

    data = list(siswa_list.values('nama', 'nomor_induk', 'nisn', 'jenis_kelamin', 'kelas__nama', 'tahun_ajaran', 'tempat_lahir', 'tanggal_lahir', 'agama', 'nama_ayah', 'nama_ibu', 'alamat', 'no_hp'))
    
    df = pd.DataFrame(data)
    
    # Rename columns for clarity
    df.rename(columns={
        'nama': 'Nama Siswa',
        'nomor_induk': 'Nomor Induk',
        'nisn': 'NISN',
        'jenis_kelamin': 'Jenis Kelamin',
        'kelas__nama': 'Kelas',
        'tahun_ajaran': 'Tahun Ajaran',
        'tempat_lahir': 'Tempat Lahir',
        'tanggal_lahir': 'Tanggal Lahir',
        'agama': 'Agama',
        'nama_ayah': 'Nama Ayah',
        'nama_ibu': 'Nama Ibu',
        'alamat': 'Alamat',
        'no_hp': 'No. HP'
    }, inplace=True)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="data_siswa.xlsx"'
    
    df.to_excel(response, index=False)
    
    return response
