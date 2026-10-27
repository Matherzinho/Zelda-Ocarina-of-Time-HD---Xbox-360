// dxtenc: the image work of make_dxt_pack.py, in C for speed (loaded with ctypes). An HD texture's RGBA8 pixels
// (bytes R, G, B, A) resized with a box filter on premultiplied colour, a sky's black frame filled from the texels
// inside first, then compressed for the Xbox 360's GPU: DXT1 when every texel is opaque, else DXT5, with every mip
// level down to 1x1 (each from the one above, weighted by alpha as the port's own HalveRgba does), one level after the
// other in a .dds file's block order, which xsdk uploads as it is.
//
//   cc -O2 -shared -fPIC -o dxtenc.so dxtenc.c -I<stb>      (stb_dxt.h, public domain, from nothings/stb)
//
// No game data here: the tool reads the player's own mod archives on their own PC and writes the result there.
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define STB_DXT_IMPLEMENTATION
#define STB_DXT_STATIC
#include "stb_dxt.h"

static int is_black(const uint8_t* p) {
	return p[0] == 0 && p[1] == 0 && p[2] == 0;
}

// Every whole black row or column at the image's edges (up to 16 deep, less than a quarter of the side) replaced by
// the first line inside that isn't black: 3DS Experience's skies carry such a frame, which a scaled or block-compressed
// edge texel would blend in (make_xbox_pack.py, fill_black_frame).
static int fill_black_frame(uint8_t* px, int w, int h) {
	int filled = 0;
	for (int side = 0; side < 4; side++) {
		const int horizontal = side < 2; // rows (top, bottom) or columns (left, right)
		const int count = horizontal ? h : w;
		const int len = horizontal ? w : h;
		const int deepest = count / 4 < 16 ? count / 4 : 16;
		int depth = 0;
		for (;;) {
			if (depth >= deepest) {
				break;
			}
			const int line = (side == 0 || side == 2) ? depth : count - 1 - depth;
			int black = 1;
			for (int i = 0; i < len && black; i++) {
				const int x = horizontal ? i : line, y = horizontal ? line : i;
				black = is_black(px + ((size_t)y * w + x) * 4);
			}
			if (!black) {
				break;
			}
			depth++;
		}
		if (!depth || depth >= count / 4) {
			continue;
		}
		const int src = (side == 0 || side == 2) ? depth : count - 1 - depth;
		for (int d = 0; d < depth; d++) {
			const int dst = (side == 0 || side == 2) ? d : count - 1 - d;
			for (int i = 0; i < len; i++) {
				const int sx = horizontal ? i : src, sy = horizontal ? src : i;
				const int dx = horizontal ? i : dst, dy = horizontal ? dst : i;
				memcpy(px + ((size_t)dy * w + dx) * 4, px + ((size_t)sy * w + sx) * 4, 4);
			}
		}
		filled += depth;
	}
	return filled;
}

// Box filter from w x h to ow x oh on premultiplied colour (any ratio: each output texel averages the input area it
// covers, partial texels weighted by their coverage).
static void resize_box(const uint8_t* in, int w, int h, uint8_t* out, int ow, int oh) {
	const double sx = (double)w / ow, sy = (double)h / oh;
	for (int y = 0; y < oh; y++) {
		const double y0 = y * sy, y1 = (y + 1) * sy;
		for (int x = 0; x < ow; x++) {
			const double x0 = x * sx, x1 = (x + 1) * sx;
			double acc[4] = { 0, 0, 0, 0 }, area = 0;
			for (int iy = (int)y0; iy < h && iy < y1; iy++) {
				const double wy = (iy + 1 < y1 ? iy + 1 : y1) - (iy > y0 ? iy : y0);
				for (int ix = (int)x0; ix < w && ix < x1; ix++) {
					const double wx = (ix + 1 < x1 ? ix + 1 : x1) - (ix > x0 ? ix : x0);
					const double wgt = wx * wy;
					const uint8_t* p = in + ((size_t)iy * w + ix) * 4;
					const double a = p[3] / 255.0;
					acc[0] += p[0] * a * wgt;
					acc[1] += p[1] * a * wgt;
					acc[2] += p[2] * a * wgt;
					acc[3] += p[3] * wgt;
					area += wgt;
				}
			}
			uint8_t* q = out + ((size_t)y * ow + x) * 4;
			if (area <= 0) {
				memset(q, 0, 4);
				continue;
			}
			const double alpha = acc[3] / area;
			for (int c = 0; c < 3; c++) {
				double v = alpha > 0 ? acc[c] / area / (alpha / 255.0) : 0;
				q[c] = (uint8_t)(v < 0 ? 0 : v > 255 ? 255 : v + 0.5);
			}
			q[3] = (uint8_t)(alpha > 255 ? 255 : alpha + 0.5);
		}
	}
}

// The next mip level, each texel the alpha-weighted average of the 2x2 above it (gfx_xenos.cpp, HalveRgba).
static void halve(const uint8_t* src, int w, int h, uint8_t* dst, int nw, int nh) {
	for (int y = 0; y < nh; y++) {
		const int y0 = y * 2 < h ? y * 2 : h - 1, y1 = y * 2 + 1 < h ? y * 2 + 1 : h - 1;
		for (int x = 0; x < nw; x++) {
			const int x0 = x * 2 < w ? x * 2 : w - 1, x1 = x * 2 + 1 < w ? x * 2 + 1 : w - 1;
			const uint8_t* p[4] = { src + ((size_t)y0 * w + x0) * 4, src + ((size_t)y0 * w + x1) * 4,
						src + ((size_t)y1 * w + x0) * 4, src + ((size_t)y1 * w + x1) * 4 };
			uint8_t* q = dst + ((size_t)y * nw + x) * 4;
			const unsigned a = p[0][3] + p[1][3] + p[2][3] + p[3][3];
			if (p[0][3] == p[1][3] && p[0][3] == p[2][3] && p[0][3] == p[3][3]) {
				for (int c = 0; c < 3; c++) {
					q[c] = (uint8_t)((p[0][c] + p[1][c] + p[2][c] + p[3][c] + 2) >> 2);
				}
				q[3] = p[0][3];
				continue;
			}
			for (int c = 0; c < 3; c++) {
				const unsigned sum = p[0][c] * p[0][3] + p[1][c] * p[1][3] + p[2][c] * p[2][3] + p[3][c] * p[3][3];
				const unsigned v = (sum + a / 2) / a;
				q[c] = (uint8_t)(v > 255 ? 255 : v);
			}
			q[3] = (uint8_t)((a + 2) >> 2);
		}
	}
}

static size_t level_bytes(int w, int h, int dxt5) {
	return (size_t)((w + 3) / 4) * ((h + 3) / 4) * (dxt5 ? 16 : 8);
}

static uint8_t* encode_level(const uint8_t* px, int w, int h, int dxt5, uint8_t* out) {
	uint8_t block[64];
	for (int by = 0; by < (h + 3) / 4; by++) {
		for (int bx = 0; bx < (w + 3) / 4; bx++) {
			for (int py = 0; py < 4; py++) {
				const int y = by * 4 + py < h ? by * 4 + py : h - 1;
				for (int pxl = 0; pxl < 4; pxl++) {
					const int x = bx * 4 + pxl < w ? bx * 4 + pxl : w - 1;
					memcpy(block + (py * 4 + pxl) * 4, px + ((size_t)y * w + x) * 4, 4);
				}
			}
			stb_compress_dxt_block(out, block, dxt5, STB_DXT_HIGHQUAL);
			out += dxt5 ? 16 : 8;
		}
	}
	return out;
}

// The most bytes hd_dxt_encode writes for an ow x oh texture (DXT5 with every level).
size_t hd_dxt_bound(int ow, int oh) {
	size_t total = 0;
	for (int w = ow, h = oh;; w = w > 1 ? w / 2 : 1, h = h > 1 ? h / 2 : 1) {
		total += level_bytes(w, h, 1);
		if (w == 1 && h == 1) {
			break;
		}
	}
	return total;
}

// rgba (w x h) to ow x oh, compressed with its levels into out (cap bytes); *dxt5 says which format; *framed whether a
// sky's frame was filled. Returns the bytes written, or 0 on failure.
size_t hd_dxt_encode(const uint8_t* rgba, int w, int h, int ow, int oh, int sky, uint8_t* out, size_t cap, int* dxt5,
		     int* framed) {
	if (w <= 0 || h <= 0 || ow <= 0 || oh <= 0 || cap < hd_dxt_bound(ow, oh)) {
		return 0;
	}
	uint8_t* src = malloc((size_t)w * h * 4);
	uint8_t* a = malloc((size_t)ow * oh * 4);
	uint8_t* b = malloc((size_t)ow * oh * 4);
	if (!src || !a || !b) {
		free(src);
		free(a);
		free(b);
		return 0;
	}
	memcpy(src, rgba, (size_t)w * h * 4);
	*framed = sky ? fill_black_frame(src, w, h) : 0;
	if (ow == w && oh == h) {
		memcpy(a, src, (size_t)w * h * 4);
	} else {
		resize_box(src, w, h, a, ow, oh);
	}
	free(src);
	int opaque = 1;
	for (size_t i = 0; i < (size_t)ow * oh && opaque; i++) {
		opaque = a[i * 4 + 3] == 255;
	}
	*dxt5 = !opaque;
	uint8_t* o = out;
	uint8_t* cur = a;
	uint8_t* next = b;
	int lw = ow, lh = oh;
	for (;;) {
		o = encode_level(cur, lw, lh, *dxt5, o);
		if (lw == 1 && lh == 1) {
			break;
		}
		const int nw = lw > 1 ? lw / 2 : 1, nh = lh > 1 ? lh / 2 : 1;
		halve(cur, lw, lh, next, nw, nh);
		uint8_t* t = cur;
		cur = next;
		next = t;
		lw = nw;
		lh = nh;
	}
	free(a);
	free(b);
	return (size_t)(o - out);
}
