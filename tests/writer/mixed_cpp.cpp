// The C++ half of INV-14's mixed program; mixed_c.c is the other. Every
// writer function is used from here, and the C file adds rows to the same
// writer. Exits 0 when the bytes are what both halves wrote. No I/O, so
// `nm -u` on its object shows only what the header itself needs.
#include "../../include/frameledger.h"

extern "C" int mixed_c_rows(fled_writer *w);

int main()
{
    static char buf[4096];
    static const char expected[] =
        "# frameledger {}\n"
        "run_id,segment,frame,category,name,depth,value\n"
        "m1,view:1,0,frame,cpu_span,0,8.250\n"
        "m1,view:1,0,frame,wall,0,16.667\n"
        "m1,view:1,0,gpu,shadows,0,1.500\n"
        "# frameledger-close {\"rows_dropped\":0,\"frames\":1}\n";
    char escaped[16];
    fled_writer w;
    const char *bytes;
    if (fled_open(&w, buf, sizeof buf, "m1", "{}", nullptr) != FLED_OK)
        return 1;
    if (mixed_c_rows(&w) != FLED_OK)
        return 2;
    if (fled_row(&w, "view:1", 0, "gpu", "shadows", 0, 1.5) != FLED_OK)
        return 3;
    if (fled_close(&w, 1) != FLED_OK)
        return 4;
    if (fled_pending(&w, &bytes) != sizeof expected - 1 ||
        memcmp(bytes, expected, sizeof expected - 1) != 0)
        return 5;
    fled_consume(&w, sizeof expected - 1);
    if (fled_pending(&w, &bytes) != 0)
        return 6;
    if (fled_json_escape(escaped, sizeof escaped, "a\"b\n") != 6 || memcmp(escaped, "a\\\"b\\n", 7) != 0)
        return 7;
    return 0;
}
