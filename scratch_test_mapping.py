import os
import sys
import django
from datetime import datetime, date

sys.path.append(os.path.abspath('app'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from thongsothuyvan.models import ThongsoSanxuat, SonghinhMnh, ThongsoGioPhat

def test():
    print("Testing Sông Hinh DB to Sheet mapping...")
    
    # Check what data is available
    print(f"ThongsoSanxuat(songhinh) count: {ThongsoSanxuat.objects.filter(nha_may='songhinh').count()}")
    print(f"SonghinhMnh count: {SonghinhMnh.objects.count()}")
    print(f"ThongsoGioPhat(songhinh) count: {ThongsoGioPhat.objects.filter(nha_may='songhinh').count()}")

if __name__ == '__main__':
    test()
