from django import forms
from django.forms import inlineformset_factory
from .models import LaporanPerkembangan, LaporanAspek, TahunAjaran, Siswa

class LaporanPerkembanganForm(forms.ModelForm):
    class Meta:
        model = LaporanPerkembangan
        fields = ['siswa', 'semester', 'status']
        widgets = {
            'siswa': forms.Select(attrs={'class': 'form-select'}),
            'semester': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

class LaporanAspekForm(forms.ModelForm):
    class Meta:
        model = LaporanAspek
        fields = ['aspek', 'deskripsi', 'foto']
        widgets = {
            'aspek': forms.Select(attrs={'class': 'form-select'}),
            'deskripsi': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'foto': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

class LaporanForm(forms.ModelForm):
    siswa = forms.ModelChoiceField(
        queryset=Siswa.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    tahun_ajaran = forms.ModelChoiceField(
        queryset=TahunAjaran.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    semester = forms.ChoiceField(
        choices=[('1','Semester 1'), ('2','Semester 2')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    class Meta:
        model = LaporanPerkembangan
        fields = ['siswa', 'tahun_ajaran', 'semester']

class RefleksiOrangTuaForm(forms.ModelForm):
    class Meta:
        model = LaporanPerkembangan
        fields = ['refleksi_orang_tua']
        widgets = {
            'refleksi_orang_tua': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
        }
