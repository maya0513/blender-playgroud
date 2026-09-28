"""Create the sRGB working texture without altering the supplied photograph."""
from PIL import Image,ImageCms
from pathlib import Path
import io
ROOT=Path(__file__).resolve().parents[1]
im=Image.open(ROOT/'photos/IMG_6955.jpeg')
assert im.size==(3024,3024)
assert im.info.get('icc_profile'),'The photograph must retain its embedded profile'
source=ImageCms.ImageCmsProfile(io.BytesIO(im.info['icc_profile']));target=ImageCms.createProfile('sRGB')
result=ImageCms.profileToProfile(im,source,target,outputMode='RGB')
(ROOT/'assets').mkdir(exist_ok=True)
result.save(ROOT/'assets/reference_srgb.png',icc_profile=ImageCms.ImageCmsProfile(target).tobytes())
print('Source profile:',ImageCms.getProfileName(source).strip(),'-> sRGB, 3024 x 3024')
