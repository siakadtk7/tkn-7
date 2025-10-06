import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tk_7.settings')
django.setup()

from main.models import AspekPerkembangan

ASPEK_CHOICES = [
    ('agama_budi_pekerti', 'Agama & Budi Pekerti'),
    ('jati_diri', 'Jati Diri'),
    ('literasi', 'Dasar Literasi'),
    ('sains_teknologi_seni_matematika', 'Sains, Teknologi, Seni & Matematika'),
    ('projek_penguatan_pancasila', 'Projek Penguatan Profil Pancasila'),
]

def populate_aspek():
    print("Populating AspekPerkembangan table...")
    for i, (kode, label) in enumerate(ASPEK_CHOICES):
        aspek, created = AspekPerkembangan.objects.get_or_create(
            nama=label,
            defaults={'urutan': i}
        )
        if created:
            print(f"Created: {label}")
        else:
            print(f"Exists: {label}")
    print("Population complete.")

if __name__ == '__main__':
    populate_aspek()
