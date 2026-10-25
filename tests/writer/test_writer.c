/* The writer's behaviour: docs/specs/FLED-0001-run-file-format.md § 4.6,
 * INV-15, INV-16, INV-17, INV-19, INV-20 and INV-22. test_compile.sh
 * builds this as C and as C++ and runs it; with a path argument it also
 * writes test_output_conforms' run there, for the analyser's `check`.
 * Exit 0 when every test passes.
 */
#include <locale.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "../../include/frameledger.h"

#define HEADER                                                                                     \
    "{\"schema\":1,\"run_id\":\"w1\",\"engine\":\"writer-test\",\"tool\":{\"name\":\"test_writer\"," \
    "\"version\":\"1.0\"},\"build_type\":\"release\",\"commit\":\"abc123\",\"dirty\":false,"         \
    "\"device\":\"test\",\"renderer\":\"test\",\"driver\":\"test\",\"api\":\"opengl-4.5\","           \
    "\"resolution\":[1920,1080],\"render_scale\":1.0,\"vsync\":false,\"pipelined\":true,"            \
    "\"display\":\"offscreen\",\"scene\":\"test\",\"inputs\":[],"                                    \
    "\"started_utc\":\"2026-10-26T12:00:00Z\"}"

/* "w1,view:1,0,frame,cpu_span,0,8.000\n": every row the sizing tests write. */
#define ROW_LEN 35

static int failures = 0;

static void expect(int ok, const char *test, const char *what)
{
    if (!ok) {
        printf("FAIL %s: %s\n", test, what);
        failures++;
    }
}

/* The bytes fled_open writes for HEADER and no static line. */
static size_t opening_len(void)
{
    static char buf[4096];
    fled_writer w;
    fled_open(&w, buf, sizeof buf, "w1", HEADER, NULL);
    return w.len;
}

/* A buffer with room for exactly ten ROW_LEN rows: a row is dropped once
   fewer than FLED_ROW_MAX bytes are free, so the eleventh finds one byte
   short. */
static size_t ten_row_cap(void)
{
    return opening_len() + FLED_CLOSE_MAX + FLED_ROW_MAX + 10 * ROW_LEN - 1;
}

/* The last row written, without its newline. */
static const char *last_row(const fled_writer *w, char *line, size_t cap)
{
    const char *bytes;
    size_t n = fled_pending(w, &bytes), start;
    if (n == 0 || n > cap)
        return "";
    start = n - 1;
    while (start > 0 && bytes[start - 1] != '\n')
        start--;
    memcpy(line, bytes + start, n - 1 - start);
    line[n - 1 - start] = '\0';
    return line;
}

/* INV-15: twenty rows into room for ten; the close line still lands and
   counts the ten drops. */
static void test_drops(void)
{
    static char buf[8192];
    fled_writer w;
    const char *bytes;
    size_t cap = ten_row_cap(), n;
    int i, dropped = 0;
    char close[128];
    fled_open(&w, buf, cap, "w1", HEADER, NULL);
    for (i = 0; i < 20; i++)
        if (fled_row(&w, "view:1", 0, "frame", "cpu_span", 0, 8.0) == FLED_DROPPED)
            dropped++;
    expect(dropped == 10, "test_drops", "ten of twenty rows dropped");
    expect(fled_close(&w, 1) == FLED_OK, "test_drops", "close succeeds");
    n = fled_pending(&w, &bytes);
    expect(n <= cap, "test_drops", "the close line fits the buffer");
    sprintf(close, "# frameledger-close {\"rows_dropped\":%d,\"frames\":1}\n", dropped);
    expect(n >= strlen(close) && memcmp(bytes + n - strlen(close), close, strlen(close)) == 0,
           "test_drops", "the close line counts every drop");
}

/* INV-16: a run written under a comma-decimal locale; test_compile.sh
   passes it to `check`. */
static void test_output_conforms(const char *path)
{
    static const char *const locales[] = {"de_DE.UTF-8", "de_DE.utf8", "de_DE", "German_Germany.1252",
                                          "de-DE"};
    static char buf[1 << 16];
    fled_writer w;
    const char *bytes, *locale = NULL;
    size_t i, n;
    long long frame;
    FILE *file;
    for (i = 0; i < sizeof locales / sizeof locales[0] && locale == NULL; i++)
        locale = setlocale(LC_ALL, locales[i]);
    expect(locale != NULL, "test_output_conforms", "a comma-decimal locale is installed");
    expect(locale == NULL || localeconv()->decimal_point[0] == ',', "test_output_conforms",
           "the locale's decimal point is a comma");
    expect(fled_open(&w, buf, sizeof buf, "w1", HEADER, "{\"draws\":\"1200\"}") == FLED_OK,
           "test_output_conforms", "open succeeds");
    for (frame = 0; frame < 5; frame++) {
        const char *segment = frame < 3 ? "view:1" : "spot:e1m1,a"; /* a comma, so quoted */
        fled_row(&w, segment, frame, "frame", "cpu_span", 0, 8.25 + (double)frame / 3);
        fled_row(&w, segment, frame, "frame", "gpu_span", 0, 10.5);
        if (frame < 4)
            fled_row(&w, segment, frame, "frame", "wall", 0, 16.667);
        fled_row(&w, segment, frame, "cpu", "shadows", 0, 1.0625);
        fled_row(&w, segment, frame, "gpu", "shadows/tiles", 1, -0.004);
        fled_row(&w, segment, frame, "ext.writer-test", "probes", 0, 123456789.123);
    }
    fled_row(&w, "spot:e1m1,a", 3, "event", "cut", 0, 1);
    expect(fled_close(&w, 5) == FLED_OK, "test_output_conforms", "close succeeds");
    setlocale(LC_ALL, "C");
    if (path == NULL)
        return;
    n = fled_pending(&w, &bytes);
    file = fopen(path, "wb");
    expect(file != NULL && fwrite(bytes, 1, n, file) == n, "test_output_conforms", "the run is written");
    if (file != NULL)
        fclose(file);
}

/* INV-17: a 65-byte name is refused whole, a 64-byte one taken. */
static void test_name_limit(void)
{
    static char buf[4096];
    char name[FLED_NAME_MAX + 2];
    fled_writer w;
    size_t before;
    memset(name, 'a', FLED_NAME_MAX + 1);
    name[FLED_NAME_MAX + 1] = '\0';
    fled_open(&w, buf, sizeof buf, "w1", HEADER, NULL);
    before = w.len;
    expect(fled_row(&w, "", 0, "cpu", name, 0, 1.0) == FLED_BAD_ARG, "test_name_limit",
           "a 65-byte name is refused");
    expect(w.len == before, "test_name_limit", "a refused row writes nothing");
    name[FLED_NAME_MAX] = '\0';
    expect(fled_row(&w, "", 0, "cpu", name, 0, 1.0) == FLED_OK, "test_name_limit",
           "a 64-byte name is taken");
    expect(fled_row(&w, "", 0, "cpu", "a b", 0, 1.0) == FLED_BAD_ARG, "test_name_limit",
           "a space in a name is refused");
}

/* INV-19: ties go away from zero. 0.0625 and -0.0625 are exact in binary,
   so the tie is real. */
static void test_rounding(void)
{
    static char buf[4096];
    char line[512];
    fled_writer w;
    fled_open(&w, buf, sizeof buf, "w1", HEADER, NULL);
    fled_row(&w, "", 0, "cpu", "a", 0, 0.0625);
    expect(strcmp(last_row(&w, line, sizeof line), "w1,,0,cpu,a,0,0.063") == 0, "test_rounding",
           "0.0625 is written 0.063");
    fled_row(&w, "", 0, "cpu", "b", 0, -0.0625);
    expect(strcmp(last_row(&w, line, sizeof line), "w1,,0,cpu,b,0,-0.063") == 0, "test_rounding",
           "-0.0625 is written -0.063");
    fled_row(&w, "", 0, "cpu", "c", 0, -0.0004);
    expect(strcmp(last_row(&w, line, sizeof line), "w1,,0,cpu,c,0,0.000") == 0, "test_rounding",
           "a negative rounding to zero is 0.000");
}

/* INV-20: NaN, infinity and anything rounding to 1e9 or more are refused
   and write nothing. */
static void test_bad_values(void)
{
    static char buf[4096];
    fled_writer w;
    size_t before;
    fled_open(&w, buf, sizeof buf, "w1", HEADER, NULL);
    before = w.len;
    expect(fled_row(&w, "", 0, "cpu", "a", 0, NAN) == FLED_BAD_ARG, "test_bad_values", "NaN");
    expect(fled_row(&w, "", 0, "cpu", "a", 0, INFINITY) == FLED_BAD_ARG, "test_bad_values", "infinity");
    expect(fled_row(&w, "", 0, "cpu", "a", 0, -INFINITY) == FLED_BAD_ARG, "test_bad_values",
           "negative infinity");
    expect(fled_row(&w, "", 0, "cpu", "a", 0, 1e9) == FLED_BAD_ARG, "test_bad_values", "1e9");
    expect(fled_row(&w, "", 0, "cpu", "a", 0, 999999999.9996) == FLED_BAD_ARG, "test_bad_values",
           "a value rounding up to 1e9");
    expect(w.len == before, "test_bad_values", "refused rows write nothing");
    expect(w.dropped == 0, "test_bad_values", "refused rows are not counted as dropped");
    expect(fled_row(&w, "", 0, "cpu", "a", 0, -999999999.999) == FLED_OK, "test_bad_values",
           "the largest value in size is taken");
}

/* INV-22: with the engine consuming after every ten rows, a buffer with
   room for ten takes thirty. */
static void test_consume_reuses(void)
{
    static char buf[8192];
    fled_writer w;
    const char *bytes;
    int i, dropped = 0;
    fled_open(&w, buf, ten_row_cap(), "w1", HEADER, NULL);
    fled_consume(&w, fled_pending(&w, &bytes));
    for (i = 0; i < 30; i++) {
        if (fled_row(&w, "view:1", 0, "frame", "cpu_span", 0, 8.0) == FLED_DROPPED)
            dropped++;
        if (i % 10 == 9) {
            expect(fled_pending(&w, &bytes) == 10 * ROW_LEN, "test_consume_reuses",
                   "ten rows pending before each consume");
            fled_consume(&w, fled_pending(&w, &bytes));
        }
    }
    expect(dropped == 0, "test_consume_reuses", "no row dropped");
}

int main(int argc, char **argv)
{
    test_drops();
    test_output_conforms(argc > 1 ? argv[1] : NULL);
    test_name_limit();
    test_rounding();
    test_bad_values();
    test_consume_reuses();
    if (failures == 0)
        printf("test_writer: all tests passed\n");
    return failures == 0 ? 0 : 1;
}
