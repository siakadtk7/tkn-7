from django.contrib import admin
from django.urls import path, include
from main import views
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.login_view, name='root'),  # <- root URL
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('admin-dashboard/', views.dashboard_admin, name='admin_dashboard'),
    
    path('guru-dashboard/', views.guru_dashboard, name='guru_dashboard'),

    path('kepala-dashboard/', views.kepala_dashboard, name='kepala_dashboard'),

    path('data-siswa/', views.data_siswa, name='data_siswa'),
    path('siswa/', views.data_siswa, name='data_siswa'),
<<<<<<< HEAD
    path('siswa/download/', views.download_siswa_excel, name='download_siswa_excel'),
=======
>>>>>>> 9b78fbe049163d23ecef90cfa98626ad3a8f1fa3
    path('siswa/tambah/', views.siswa_tambah, name='siswa_tambah'),
    path('siswa/edit/<int:pk>/', views.siswa_edit, name='siswa_edit'),
    path("siswa/delete/<int:pk>/", views.siswa_delete, name="siswa_delete"), 
    path('kelas/tambah/', views.tambah_kelas, name='tambah_kelas'),
    path('kelas/hapus/<int:kelas_id>/', views.hapus_kelas, name='hapus_kelas'),
    path('kelas/edit/<int:kelas_id>/', views.edit_kelas, name='edit_kelas'),

    path('data-guru/', views.data_guru, name='data_guru'),
    path('hapus-guru/<int:guru_id>/', views.guru_delete, name='hapus_guru'),
    
    path('absensi/submit/', views.absensi_submit, name='absensi_submit'),
    path('absensi/', views.absensi, name='absensi'),
    path('absensi/download/', views.absensi_download_pdf, name='absensi_download_pdf'),

    path('laporan-perkembangan/', views.laporan_perkembangan, name='laporan_perkembangan'),
    path('laporan/tambah/', views.laporan_tambah, name='laporan_tambah'),
    path('laporan/edit/<int:pk>/', views.laporan_edit, name='laporan_edit'),
    path('laporan/hapus/<int:pk>/', views.laporan_hapus, name='laporan_hapus'),
    path('laporan/tambah/<int:siswa_id>/', views.laporan_tambah, name='laporan_tambah'),
    path('laporan/tambah-aspek-ajax/', views.tambah_aspek_ajax, name='tambah_aspek_ajax'),
    path('laporan/hapus-aspek-ajax/<int:aspek_id>/', views.hapus_aspek_ajax, name='hapus_aspek_ajax'),
    path('laporan/edit-aspek-ajax/<int:aspek_id>/', views.edit_aspek_ajax, name='edit_aspek_ajax'),
    
    path('biodata/<int:siswa_id>/', views.cetak_biodata, name='cetak_biodata'),

    path('raport-digital/<int:siswa_id>/biodata-pdf/', views.biodata_pdf, name='biodata_pdf'),

    path('raport_digital/', views.raport_digital, name='raport_digital'),
    path('raport-digital/tambah-refleksi-ajax/', views.tambah_refleksi_ajax, name='tambah_refleksi_ajax'),
    path('raport-digital/edit-refleksi-ajax/<int:refleksi_id>/', views.edit_refleksi_ajax, name='edit_refleksi_ajax'),
    path('raport-digital/hapus-refleksi-ajax/<int:refleksi_id>/', views.hapus_refleksi_ajax, name='hapus_refleksi_ajax'),

    path('raport/cetak/<int:siswa_id>/', views.cetak_raport, name='cetak_raport'),
    path('raport/pdf/<int:laporan_id>/', views.raport_pdf, name='raport_pdf'),
    path('manage-users/', views.manage_users, name='manage_users'),


    path('raport-digital/manage-active-reflections/', views.manage_active_reflections_ajax, name='manage_active_reflections'),
    path('raport-digital/manage-active-reflections/<int:comment_id>/', views.manage_active_reflections_ajax, name='manage_active_reflection_detail'),

    path('manage-users/edit/<int:user_id>/', views.user_edit, name='user_edit'),
    path('manage-users/delete/<int:user_id>/', views.user_delete, name='user_delete'),
    path('manage-users/create-for-guru/<int:guru_id>/', views.create_user_for_guru, name='create_user_for_guru'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
