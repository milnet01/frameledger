/* The C half of INV-14's mixed program: mixed_cpp.cpp opens a writer and
 * hands it here, so one writer is used from C and C++ files of the same
 * program. It does no I/O, so `nm -u` on its object shows only what the
 * header itself needs.
 */
#include "../../include/frameledger.h"

int mixed_c_rows(fled_writer *w);

int mixed_c_rows(fled_writer *w)
{
    return fled_row(w, "view:1", 0, "frame", "cpu_span", 0, 8.25) |
           fled_row(w, "view:1", 0, "frame", "wall", 0, 16.667);
}
