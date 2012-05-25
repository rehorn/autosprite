#!/usr/bin/python
#encoding=utf-8
#python2.6

import sys, os, re
from PIL import Image as PImage

# default setting
CONFIG = {
    'VERSION': '0.0.1',
    'TRANSPARENT': (255, 255, 255, 0),
    'IS_QUIET': False,
    'ROOT_SPRITE_NAME': 'app-sprite',
    'ALLOW_IMG_EXT': ['png', 'jpg', 'jpeg', 'gif'],
    'ALLOW_CSS_EXT': ['css'],
    'PACKER': 'vertical',
    'REPLACER': 'simple',
    'CSS_OUTPUT': './',
    'SPRITE_OUTPUT': './',
    'REGX_URL': r'url\s*\(\s*([\'\"]?)([^\'\"\)]+)\\1\s*\)'
}

def log(msg, spliteLine = ''):
    if not CONFIG['IS_QUIET']:
        print msg, spliteLine

def checkExt(path, allowExts = CONFIG['ALLOW_IMG_EXT']):
    exts = '|'.join(allowExts)
    # compile regex str to a RegexObject;
    # test=>is exits; exec=>return first match val; 
    # match=>return match array; search=>indexOf; replace; split
    extRegx = re.compile('.+\.(%s)$' % exts, re.IGNORECASE)
    return not path.startswith('.') and extRegx.match(path)

# error handling
class PILError(Exception):

    """PIL Python package is not installed"""
    err_code = 1


# sprite packer algorithm
class VerticalPacker(object):

    def process(self, sprite):
        y = 0
        for image in sprite.images:
            image.x = 0
            image.y = y
            y += image.absoluteHeight


# packer mapping
PACKER = {
    'vertical': VerticalPacker
}

# css replacer
class SimpleReplacer(object):

    def process(self, cssFile):
        for line in open(cssFile.path).xreadlines():
            

REPLACER = {
    'simple': SimpleReplacer
}

# business class
class Image(object):

    def __init__(self, name, sprite):
        self.x = None
        self.y = None
        self.name = name
        self.sprite = sprite
        self.fileName, self.format = name.rsplit('.', 1)

        imagePath = os.path.join(sprite.path, name)
        # imagePath = imagePath.replace('\\', '/')
        self.absPath = os.path.abspath(imagePath)
        imageFile = open(imagePath, "rb")

        try:
            sourceImage = PImage.open(imageFile)
            sourceImage.load()
            self.image = PImage.new('RGBA', sourceImage.size, (0, 0, 0, 0))

            if imageFile.mode == 'L':
                alpha = sourceImage.split()[0]
                transparency = sourceImage.info.get('transparency')
                mask = PImage.eval(alpha, lambda a: 0 if a == transparency else 255)
                self.image.paste(sourceImage, (0, 0), mask = mask)
            else:
                self.image.paste(sourceImage, (0, 0))

        except IOError, e:
            raise PILError(e.args[0].split()[1])

        imageFile.close()

        self.width, self.height = self.image.size
        self.absoluteWidth = self.width
        self.absoluteHeight = self.height

class Sprite(object):

    def __init__(self, name, path, manager):
        log('Spite init')
        self.name = name
        self.manager = manager
        self.images = []
        self.path = path
        self.process();

    def process(self):
        log('Sprite process')
        packer = PACKER.get(CONFIG['PACKER'])
        self.packer = packer()
        self.images = self._locateImages()

        self.packer.process(self)

    def save(self):
        log("Creating [%s] image file..." % self.name)
        outputPath = CONFIG['SPRITE_OUTPUT']

        # cal sprite canvas width & height
        width = height = 0

        for image in self.images:
            x = image.x + image.absoluteWidth
            y = image.y + image.absoluteHeight
            if width < x:
                width = x
            if height < y:
                height = y

        # Create the sprite canvas
        canvas = PImage.new('RGBA', (width, height), (0, 0, 0, 0))

        for image in self.images:
            canvas.paste(image.image, (image.x, image.y))

        # Save png
        spriteName = '%s.png' % self.fileName
        spritePath = os.path.join(outputPath, spriteName)

        args, kwargs = [spritePath], dict(optimize = True)
        canvas.save(*args, **kwargs)
        

    def _locateImages(self):
        log('  >> _locateImages')
        files = sorted(os.listdir(self.path))
        images = [Image(f, self) for f in files if checkExt(f, CONFIG['ALLOW_IMG_EXT'])]

        for image in images:
            log('    images %s ' % image.name)

        return sorted(images)

    @property
    def fileName(self):
        return self.name

class SpriteManager(object):

    def __init__(self, path, output):
        log('SpriteManager init')
        self.path = path
        self.output = output
        self.sprites = []

    def process(self):
        log('generateSprite')
        # sprite images @ root
        self.generateSprite(self.path, CONFIG['ROOT_SPRITE_NAME'])
        # sprite images @ sub folders (module)
        for spriteName in os.listdir(self.path):
            path = os.path.join(self.path, spriteName)
            if os.path.isdir(path) and not spriteName.startswith('.'):
                self.generateSprite(path, spriteName)

        self.saveSprite()

    def generateSprite(self, path, spriteName):
        log('generate %s' % spriteName)
        sprite = Sprite(spriteName, path, self)
        self.sprites.append(sprite)

    def saveSprite(self):
        log('saveSprite')
        for sprite in self.sprites:
            sprite.save()

class CssFile(object):

    def __init__(self, path):
        self.path = path
        pass

    def process(self):
        replacer = REPLACER.get(CONFIG['REPLACER'])
        self.replacer = replacer
        self.replacer.process(self)

class CssManager(object):

    def __init__(self, path, output):
        log('CssReplaceManager init')
        self.path = path
        self.output = output
        self.cssFiles = []

    def _locateCss(self):
        log('_locateCss')
        files = sorted(os.listdir(self.path))
        for root, dirs, files in os.walk(self.path, True):
            for f in files:
                if checkExt(f, CONFIG['ALLOW_CSS_EXT']):
                    css = CssFile(f)
                    self.cssFiles.append(css)

    def _replaceCss(self):
        log('_replaceCss css file...')
        for cssFile in self.cssFiles:

        

    def process(self):
        log('CssReplaceManager process')
        self._locateCss()
        self._replaceCss();

# main
def main():
    imgSource = './images/'
    imgOutput = None
    cssSource = './css/'
    cssOutput = None
    spriteMan = SpriteManager(imgSource, imgOutput)
    spriteMan.process()
    cssMan = CssManager(cssSource, cssOutput)

if __name__ == '__main__':
    log('AutoSprite Start', 80 * '*')
    main()
    log('AutoSprite Finished', 80 * '*')
