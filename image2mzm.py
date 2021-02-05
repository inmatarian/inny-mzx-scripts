import argparse
import logging
import struct
from PIL import Image


DEFAULT_PALETTE = [
    [0, 0, 0], [0, 0, 42], [0, 42, 0], [0, 42, 42], [42, 0, 0], [42, 0, 42],
    [42, 21, 0], [42, 42, 42], [21, 21, 21], [21, 21, 63], [21, 63, 21],
    [21, 63, 63], [63, 21, 21], [63, 21, 63], [63, 63, 21], [63, 63, 63]
]


def build_parser():
    parser = argparse.ArgumentParser(description='yo momma')
    parser.add_argument('input', help='input bitmap filename')
    parser.add_argument('output', help='output mzb filename')
    parser.add_argument('--width', help='output mzb width', type=int, default=80)
    parser.add_argument('--height', help='output mzb height', type=int, default=25)
    parser.add_argument('--char-width', help='char width', type=int, default=8)
    parser.add_argument('--char-height', help='char height', type=int, default=14)
    parser.add_argument('--palette', help='palette filename for color matching')
    parser.add_argument('--chars', default='176,177,178,219',
        help='gradient comma-separated list from least to most (default: 176,177,178,219)')
    parser.add_argument('--debug', action="store_const", dest='loglevel',
                        const=logging.DEBUG, default=logging.WARNING)
    parser.add_argument('-v', '--verbose', action="store_const", dest='loglevel', const=logging.INFO)
    return parser


def get_palette(args):
    if not 'palette' in args or args.palette is None:
        return DEFAULT_PALETTE
    with open(args.palette, mode='rb') as f:
        k = f.read(48)
    pal = []
    j = 0
    logging.debug(len(k))
    for i in range(16):
        pal.append([k[j], k[j+1], k[j+2]])
        j+=3
    return pal


# mzx's 6bit nested palettes up to pillow's 8bit flat palette
def make_8bit_palette(pal6bit):
    return list(map(lambda x: (x*4) + (x//16), [item for sublist in pal6bit for item in sublist]))


def get_chars(args):
    return list(map(int, args.chars.split(',')))


# https://stackoverflow.com/a/29438149
def quantize_image(src, dst, dither=0):
    src.load()
    dst.load()
    assert dst.mode == 'P'
    assert src.mode == 'RGB' or src.mode == 'L'
    im = src.im.convert('P', int(bool(dither)), dst.im)
    try:
        return src._new(im)
    except:
        return src._makeself(im)


# gimme back a mzx char and color from a square's histogram
def rank_histogram_to_col_and_char(hist, mzx_pal, mzx_chars):
    ranking = sorted(zip(hist, range(len(hist))), key=lambda tup: tup[0], reverse=True)
    (winner, second) = (ranking[0], ranking[1])
    winner_col = winner[1] % 16
    second_col = second[1] % 16
    winner_ratio = winner[0] / (winner[0] + second[0])
    winner_char_index = round(winner_ratio*(len(mzx_chars)-1))
    # logging.debug(f"char {winner_ratio} -- {winner_char_index}")
    char = mzx_chars[winner_char_index]
    color = winner_col + (second_col * 16)
    return (char, color)


def mad_science(args, im, pil_pal, mzx_pal, mzx_chars):
    # mangle the image's aspect ratio into mzx's 640x350 whatever
    im2 = im.resize((args.width*args.char_width, args.height*args.char_height))
    pp = Image.new('P', (16, 16))
    pp.putpalette(pil_pal * 16) # 16x16 = 256 colors
    newim = quantize_image(im2, pp, 'dither')
    
    layer = []
    for y in range(args.height):
        for x in range(args.width):
            lx = x * args.char_width
            uy = y * args.char_height
            rx = lx + args.char_width
            dy = uy + args.char_height
            subim = newim.crop((lx, uy, rx, dy))
            hist = subim.histogram()
            layer.append(rank_histogram_to_col_and_char(hist, mzx_pal, mzx_chars))

    return layer


# https://www.digitalmzx.com/fileform.html#mzm
def write_mzm(args, layer):
    header_format = '<ccccHHIBBBBBxxx' # little endian
    logging.debug(f"header format: {header_format}, size: {struct.calcsize(header_format)}")
    assert struct.calcsize(header_format) == 20
    header = struct.pack(header_format, 
                         b'M', b'Z', b'M', b'3', # magic
                         args.width, # width
                         args.height, # height
                         0,     # no robot data location
                         0,     # no number of robots
                         1,     # storage mode layer
                         0,     # not a savegame
                         0x5c,  # world version minor
                         2      # world version major
    )
    logging.debug(f'output header: {len(header)} --> {header}')
    file_bytes = bytearray([b for pair in layer for b in pair])
    with open(args.output, mode="wb") as f:
        f.write(header)
        f.write(file_bytes)

    return None


def main(args):
    logging.info(f'mzb size: {args.width} {args.height}')
    logging.info(f'char size: {args.char_width} {args.char_height}')

    logging.info(f'palette: {args.palette}')
    mzx_pal = get_palette(args)
    logging.debug(f'mzx palette: {mzx_pal}')
    pil_pal = make_8bit_palette(mzx_pal)
    logging.debug(f'pil palette: {pil_pal}')

    chars = get_chars(args)
    # logging.debug(f'chars: {chars}')

    with Image.open(args.input) as im:
        logging.info(f'{args.input}: {im.format} {im.size}x{im.mode}')
        layer = mad_science(args, im, pil_pal, mzx_pal, chars)

    logging.debug(f"layer: {layer}")

    logging.info(f'output filename: {args.output}')
    write_mzm(args, layer)

    logging.info('done')
    return None


if __name__ == '__main__':
    args = build_parser().parse_args()
    logging.basicConfig(level=args.loglevel)
    main(args)
