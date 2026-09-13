# ansiconv

Convert terminal output between ANSI SGR escape sequences and HTML.

Build logs, CI output, and command captures usually come out of the
terminal full of colour and style codes (`\x1b[1;31m`, `\x1b[0m`, and so
on). Dropping that raw text into a web page just shows the escape bytes
as garbage, and stripping them loses the colour information you probably
wanted to keep. `ansiconv` converts one direction to `<span>`-based HTML
and back, so a terminal recording can go through a browser and come back
out looking the same.

It understands reset, bold/italic/underline on and off, the 16 named
foreground/background colours (including bright variants), the 256-colour
palette (`\x1b[38;5;n`/`\x1b[48;5;n`), and 24-bit truecolor
(`\x1b[38;2;r;g;b`/`\x1b[48;2;r;g;b`). Named and 256-colour codes turn into
CSS classes; truecolor turns into an inline `style` attribute since there's
no finite class to hand it. Codes outside that set (blink, strikethrough,
cursor movement, ...) aren't modeled (see Roadmap in the repo).

Newlines in the input become `<br>` tags in the output (`<br />` with
`--self-closing-br`), and the reverse conversion turns `<br>`/`<br />` back
into `\n`, so a round trip through both directions preserves line breaks.

The `ansi-` prefix on generated class names (`ansi-bold`, `ansi-fg-red`, ...)
can be changed with `--class-prefix`/`class_prefix=`, which is read the same
way on the way back so `to-ansi` still recognizes its own classes.

## Strict vs. lenient

By default the converter is strict: any escape sequence or HTML tag it
doesn't recognize raises an error and stops the conversion. That's the
right default because a silently-mangled log is worse than a loud
failure — you want to know your input had something you didn't expect.

Pass `--lenient` to instead skip anything unrecognized and keep going.
Reach for it when you're converting output you don't control, such as a
log file with cursor-movement codes or blink/strikethrough mixed in, and
you'd rather lose that formatting than lose the whole run.

## Usage

```
$ python3 -c "print('\x1b[1;31mERROR\x1b[0m: build failed')" | python -m ansiconv.cli to-html
<span class="ansi-bold ansi-fg-red">ERROR</span>: build failed
```

Round trip back to ANSI:

```
$ echo '<span class="ansi-bold ansi-fg-red">ERROR</span>: build failed' \
    | python -m ansiconv.cli to-ansi
```

Working with files and unsupported input:

```
$ python -m ansiconv.cli to-html build.log -o build.html      # strict: stops on the first oddity
$ python -m ansiconv.cli to-html build.log -o build.html --lenient   # best effort
```

As a library:

```python
from ansiconv import ansi_to_html, html_to_ansi, ConversionError

html = ansi_to_html("\x1b[32mok\x1b[0m")
try:
    ansi_to_html("\x1b[5mblink\x1b[0m")
except ConversionError:
    ...  # blink isn't modeled, so strict mode rejects it
```

## Status

Early skeleton. The core SGR <-> HTML mapping works and is covered by
the strict/lenient split described above; see the roadmap for what's
still missing.
