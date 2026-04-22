from django.core.management.base import BaseCommand
from hamperapp.models import Hamper
from PIL import Image
from django.core.files.base import ContentFile
from io import BytesIO


class Command(BaseCommand):
    help = 'Optimize all unoptimized hamper images'

    def handle(self, *args, **options):
        hampers = Hamper.objects.all()
        optimized_count = 0
        
        for hamper in hampers:
            if hamper.image:
                try:
                    # Open image
                    img = Image.open(hamper.image.path)
                    original_size = hamper.image.size
                    
                    # Convert RGBA to RGB
                    if img.mode in ('RGBA', 'LA'):
                        rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                        rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        img = rgb_img
                    
                    # Resize if too large
                    max_width = 1200
                    if img.width > max_width:
                        ratio = max_width / img.width
                        new_height = int(img.height * ratio)
                        img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                    
                    # Save with compression
                    output = BytesIO()
                    img.save(output, format='JPEG', quality=80, optimize=True)
                    output.seek(0)
                    
                    # Save back
                    hamper.image.save(hamper.image.name, ContentFile(output.read()), save=False)
                    hamper.save(update_fields=['image'])
                    
                    new_size = hamper.image.size
                    optimized_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Optimized: {hamper.name} '
                            f'({original_size / 1024:.1f}KB → {new_size / 1024:.1f}KB)'
                        )
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'✗ Error optimizing {hamper.name}: {e}')
                    )
        
        self.stdout.write(
            self.style.SUCCESS(f'\nTotal optimized: {optimized_count} images')
        )
