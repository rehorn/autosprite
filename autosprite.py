#!/usr/bin/python
#encoding=utf-8
#python2.6

import sys, os, re, copy, hashlib, commands, time
from PIL import Image as PImage

# default setting
CONFIG = {
    'VERSION': '0.1.1',
    'TRANSPARENT': (255, 255, 255, 0),
    'IS_QUIET': False,
    'INDENT': 4,
    'AUTO_VERSION': 1,
    'ROOT_SPRITE_NAME': 'app-sprite',
    'ALLOW_IMG_EXT': ['png', 'jpg', 'jpeg', 'gif'],
    'ALLOW_CSS_EXT': ['css'],
    # 'PACKER': 'horizontal',
    'PACKER': 'packed',
    'REPLACER': 'simple',
    'IMG_ORDER': 'maxside',
    'CSS_INPUT': './css/',
    'IMG_INPUT': './images/',
    # 'IMG_INPUT': './last-guardian-sprites/',
    'CSS_OUTPUT': './',
    'SPRITE_OUTPUT': './images2/',
    'SVN_LAST_UPDATE_REGX': 'Last Changed Date\:\s*(.+)\n*',
    'IMAGE_URL_REGX': 'url\(("|\')?(.*?)("|\')?\)'
}

# cache all images
CACHE = {}
ORDERINGS = ['maxside', 'width', 'height', 'area']

# alias
opath = os.path


def log(msg, spliteLine = ''):
    if not CONFIG['IS_QUIET']:
        print msg, spliteLine

def checkExt(path, allowExts = CONFIG['ALLOW_IMG_EXT']):
    exts = '|'.join(allowExts)
    # compile regex str to a RegexObject;
    # test=>is exits; exec=>return first match val; 
    # match=>return match array; search=>indexOf; replace; split
    extRegx = re.compile('.+\.(%s)$' % exts, re.IGNORECASE)
    noSpriteRegx = re.compile('.+-n\.(%s)$' % exts, re.IGNORECASE)
    xRepeatRegx = re.compile('.+-x\.(%s)$' % exts, re.IGNORECASE)
    yRepeatRegx = re.compile('.+-y\.(%s)$' % exts, re.IGNORECASE)
    return not path.startswith('.') and not noSpriteRegx.match(path) and not xRepeatRegx.match(path) and not yRepeatRegx.match(path) and extRegx.match(path)

def mkdir(path):
    path = opath.dirname(path)
    if not opath.exists(path):
        os.makedirs(path)

def getFileSvn(path):
    pass

# error handling
class PILError(Exception):

    """PIL Python package is not installed"""
    err_code = 1

class PackedSortError(Exception):

    """packed packer not sort currectly
    can't fit block into root - this should not happen if images are pre-sorted correctly
    """
    err_code = 11


# sprite packer algorithm
# reference: 
# sprite-factory: https://github.com/jakesgordon/sprite-factory
# glue: https://github.com/jorgebastida/glue
class VerticalPacker(object):

    def process(self, sprite):
        y = 0
        for image in sprite.images:
            image.x = 0
            image.y = y
            y += image.absoluteHeight

class HorizontalPacker(object):

    def process(self, sprite):
        x = 0
        for image in sprite.images:
            image.y = 0
            image.x = x
            x += image.absoluteWidth

# packed-packer: http://codeincomplete.com/posts/2011/5/7/bin_packing/example/
# packed-js-ver: http://codeincomplete.com/posts/2011/5/7/bin_packing/growing_packer.js
class PackedNode(object):

    def __init__(self, x=0, y=0, width=0, height=0, used=False,
                 down=None, right=None):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.used = used
        self.right = right
        self.down = down

    def find(self, node, width, height):
        if node.used:
            return self.find(node.right, width, height) or \
                   self.find(node.down, width, height)
        elif node.width >= width and node.height >= height:
            return node
        return None

    def grow(self, width, height):
        can_grow_d = width <= self.width
        can_grow_r = height <= self.height
        should_grow_r = can_grow_r and self.height >= (self.width + width)
        should_grow_d = can_grow_d and self.width >= (self.height + height)

        if should_grow_r:
            return self.grow_right(width, height)
        elif should_grow_d:
            return self.grow_down(width, height)
        elif can_grow_r:
            return self.grow_right(width, height)
        elif can_grow_d:
            return self.grow_down(width, height)
        else:
            raise PackedSortError()
        return None

    def grow_right(self, width, height):
        old_self = copy.copy(self)
        self.used = True
        self.x = self.y = 0
        self.width += width
        self.down = old_self
        self.right = PackedNode(x = old_self.width,
                                 y = 0,
                                 width = width,
                                 height = self.height)

        node = self.find(self, width, height)
        if node:
            return self.split(node, width, height)
        return None

    def grow_down(self, width, height):
        old_self = copy.copy(self)
        self.used = True
        self.x = self.y = 0
        self.height += height
        self.right = old_self
        self.down = PackedNode(x = 0,
                                y = old_self.height,
                                width = self.width,
                                height = height)

        node = self.find(self, width, height)
        if node:
            return self.split(node, width, height)
        return None

    def split(self, node, width, height):
        node.used = True
        node.down = PackedNode(x = node.x,
                                y = node.y + height,
                                width = node.width,
                                height = node.height - height)
        node.right = PackedNode(x = node.x + width,
                                 y = node.y,
                                 width = node.width - width,
                                 height = height)
        return node


class PackedPacker(object):

    def process(self, sprite):
        if not len(sprite.images):
            log('__ no images to packed ___')
            return

        root = PackedNode(width = sprite.images[0].absoluteWidth,
                    height = sprite.images[0].absoluteHeight)

        # Loot all over the images creating a binary tree
        for image in sprite.images:
            node = root.find(root, image.absoluteWidth, image.absoluteHeight)
            if node:  # Use this node
                node = root.split(node, image.absoluteWidth,
                                        image.absoluteHeight)
            else:  # Grow the canvas
                node = root.grow(image.absoluteWidth, image.absoluteHeight)

            image.x = node.x
            image.y = node.y

# packer mapping
PACKER = {
    'vertical': VerticalPacker,
    'horizontal': HorizontalPacker,
    'packed': PackedPacker
}

# css replacer
class SimpleReplacer(object):

    def process(self, cssFile):
        log('SimpleReplacer')
        imgRegx = re.compile(CONFIG['IMAGE_URL_REGX'], re.IGNORECASE)
        t = []
        for line in open(cssFile.path).xreadlines():
            imgUrl = imgRegx.search(line)
            if imgUrl:
                orgUrl = imgUrl.group(2)
                orgUrl = orgUrl if orgUrl.find('?') == -1 else orgUrl[0:orgUrl.find('?')]
                dirName =  opath.dirname(cssFile.path)
                url = opath.join(dirName, orgUrl)
                absPath = opath.abspath(url)
                img = CACHE.get(absPath)
                if img:
                    spriteDir = opath.dirname(img.sprite.output)
                    cssDir = opath.dirname(cssFile.output)
                    relPath = opath.relpath(spriteDir, cssDir)
                    spriteRelPath = opath.join(relPath, img.sprite.fileName)
                    t.append(imgRegx.sub('url(\"%s?v=%s\")' % (spriteRelPath.replace('\\','/'), img.sprite.md5), line))
                    t.append('%sbackground-position: -%spx -%spx;\n' % ( ' ' * CONFIG['INDENT'], img.x, img.y))
                else:
                    if(CONFIG['AUTO_VERSION']):
                        output = commands.getoutput("svn info %s" % absPath)
                        ver = re.compile(CONFIG['SVN_LAST_UPDATE_REGX']).search(output)
                        ver = ver.group(1) if ver else time.strftime('%Y%m%d')
                        t.append(imgRegx.sub('url(\"%s?v=%s\")' % (orgUrl, ver), line))
            else:
                t.append(line)

        mkdir(cssFile.output)
        open(cssFile.output,"w").write("".join(t))
        log('save css file ' + cssFile.output)

REPLACER = {
    'simple': SimpleReplacer
}

# business class
class Image(object):

    def __init__(self, name, sprite):
        self.x = 0
        self.y = 0
        self.name = name
        self.sprite = sprite
        self.fileName, self.format = name.rsplit('.', 1)

        imagePath = opath.join(sprite.path, name)
        # imagePath = imagePath.replace('\\', '/')
        self.absPath = opath.abspath(imagePath)
        CACHE[self.absPath] = self
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

    def __lt__(self, img):
        ordering = CONFIG['IMG_ORDER']
        ordering = ordering[1:] if ordering.startswith('-') else ordering

        if ordering not in ORDERINGS:
            raise InvalidImageOrderingError(ordering)

        if ordering == 'width':
            return self.absoluteWidth <= img.absoluteWidth
        elif ordering == 'height':
            return self.absoluteHeight <= img.absoluteHeight
        elif ordering == 'area':
            return self.absoluteWidth * self.absoluteHeight <= \
                   img.absoluteWidth * img.absoluteHeight
        else:
            return max(self.absoluteWidth, self.absoluteHeight) <= \
                   max(img.absoluteWidth, img.absoluteHeight)

class Sprite(object):

    def __init__(self, name, path, manager):
        log('Spite init')
        self.name = name
        self.manager = manager
        self.images = []
        self.path = path
        self.output = ''
        self.process();

    def process(self):
        log('Sprite process')
        packer = PACKER.get(CONFIG['PACKER'])
        self.packer = packer()
        self.images = self._locateImages()

        self.packer.process(self)

    def save(self):
        log("Creating [%s] image file..." % self.name)
        outputPath = self.manager.output

        if not len(self.images):
            log('__ no images to sprite ___')
            return

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
        spriteName = self.fileName
        spritePath = opath.join(outputPath, spriteName)
        self.output = spritePath

        mkdir(spritePath)
        args, kwargs = [spritePath], dict(optimize = True)
        canvas.save(*args, **kwargs)
        

    def _locateImages(self):
        log('  >> _locateImages')
        files = sorted(os.listdir(self.path))
        images = [Image(f, self) for f in files if checkExt(f, CONFIG['ALLOW_IMG_EXT'])]

        for image in images:
            log('    images %s ' % image.name)

        # packed packer algothm is not support reverse ordering
        pack = CONFIG['PACKER']
        return sorted(images, reverse = not (pack != 'packed' and CONFIG['IMG_ORDER'][0] != '-'))

    @property
    def fileName(self):
        return '%s.png' % self.name

    @property
    def md5(self):
        m = hashlib.md5()
        spriteFile = open(self.output, 'rb')
        m.update(spriteFile.read())
        spriteFile.close()
        md5 = m.hexdigest()
        return '%s%s' % (md5[0:3], md5[-3:])

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
            path = opath.join(self.path, spriteName)
            if opath.isdir(path) and not spriteName.startswith('.'):
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

    def __init__(self, path, output):
        self.path = path
        self.output = output
        pass

    def process(self):
        replacer = REPLACER.get(CONFIG['REPLACER'])
        self.replacer = replacer()
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
                    css = CssFile(opath.join(self.path, f), opath.join(self.output, f))
                    self.cssFiles.append(css)

    def _replaceCss(self):
        log('_replaceCss css file...')
        for cssFile in self.cssFiles:
            cssFile.process()

    def process(self):
        log('CssReplaceManager process')
        self._locateCss()
        self._replaceCss();

# main
def main():
    imgSource = CONFIG['IMG_INPUT']
    imgOutput = CONFIG['SPRITE_OUTPUT']
    cssSource = CONFIG['CSS_INPUT']
    cssOutput = CONFIG['CSS_OUTPUT']
    spriteMan = SpriteManager(imgSource, imgOutput)
    spriteMan.process()
    cssMan = CssManager(cssSource, cssOutput)
    cssMan.process()

if __name__ == '__main__':
    log('AutoSprite Start', 80 * '*')
    main()
    log('AutoSprite Finished', 80 * '*')
