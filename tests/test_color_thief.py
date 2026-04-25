import pytest
import asyncio
import struct
import zlib

from utils.color_thief import get_dominant_color, _rgb_to_hsv, _most_vibrant, _decode_png, _decode_jpeg
import config

class MockResponse:
    def __init__(self, status, data):
        self.status = status
        self.data = data
    async def read(self): return self.data
    async def __aenter__(self): return self
    async def __aexit__(self, exc_type, exc, tb): pass

class MockSession:
    def __init__(self, status, data):
        self.status = status
        self.data = data
        self.get_called = False
    
    def get(self, url, **kwargs):
        self.get_called = True
        return MockResponse(self.status, self.data)

def create_fake_png():
    ihdr_data = struct.pack(">IIBB", 1, 1, 8, 2) + b"\x00\x00\x00"
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + b"1234"
    idat_data = zlib.compress(b"\x00\xff\x00\x00")
    idat = struct.pack(">I", len(idat_data)) + b"IDAT" + idat_data + b"1234"
    iend = struct.pack(">I", 0) + b"IEND" + b"1234"
    return b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend

@pytest.mark.asyncio
async def test_get_dominant_color():
    fake_png = create_fake_png()
    session = MockSession(200, fake_png)
    
    import utils.color_thief
    utils.color_thief._COLOR_CACHE.clear()
    
    color = await get_dominant_color("http://thumb", session=session)
    assert color != config.COLOR_NOW_PLAYING
    assert color == 0xFF0000
    
    # Test cache hit
    session.get_called = False
    color2 = await get_dominant_color("http://thumb", session=session)
    assert color == color2
    assert session.get_called == False
    
    # Test fallback
    color3 = await get_dominant_color(None, session=session)
    assert color3 == config.COLOR_NOW_PLAYING
    
    # Test error
    session_err = MockSession(500, b"")
    color4 = await get_dominant_color("http://thumb2", session=session_err)
    assert color4 == config.COLOR_NOW_PLAYING

def test_rgb_to_hsv():
    assert _rgb_to_hsv(255, 0, 0) == (0.0, 1.0, 1.0)

def test_most_vibrant():
    assert _most_vibrant([]) == config.COLOR_NOW_PLAYING
    assert _most_vibrant([(255, 0, 0), (10, 10, 10)]) == 0xFF0000

def test_decode_png():
    assert _decode_png(b"bad") == []
    assert _decode_png(create_fake_png()) == [(255, 0, 0)]
    
def test_decode_jpeg():
    # JPEG with SOS marker (0xDA)
    jpeg = b"\xff\xd8\xff\xda\x00\x08" + (b"\xaa\xbb\xcc" * 100)
    # the mock jpeg should yield some pixels
    pixels = _decode_jpeg(jpeg)
    assert len(pixels) > 0
