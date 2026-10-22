package id.dsx.mobile.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

data class CodeSnippet(val label: String, val code: String)

/**
 * Snippet templates. In Kotlin raw strings, \n is two characters (backslash + n),
 * which is exactly what DSX expects for spacer cells.
 */
val DSX_SNIPPETS = listOf(
    CodeSnippet(
        "Kop teks",
        """
TABLE(
  border="bottom",
  border_width=1.5,
  border_color="000000",
  cell_padding=0.08cm,
  widths=["*"],
  rows=[[CELL([
    BOLD("NAMA LEMBAGA"),
    "\n",
    ITALIC("Alamat / kontak")
  ], align="center")]]
)
""".trimStart(),
    ),
    CodeSnippet(
        "Kop + logo",
        """
TABLE(
  border="bottom",
  border_width=1.5,
  border_color="000000",
  cell_padding=0.08cm,
  widths=["2.4cm", "*"],
  rows=[[
    CELL([IMAGE("assets/logo.png")], align="center", valign="center"),
    CELL([BOLD("NAMA LEMBAGA"), "\n", ITALIC("Alamat")], align="center", valign="center")
  ]]
)
""".trimStart(),
    ),
    CodeSnippet(
        "TTD 2 kolom",
        """
TABLE(
  border="none",
  cell_padding=0.05cm,
  widths=["*", "*"],
  rows=[
    [CELL("Mengetahui,", align="center"), CELL("Hormat kami,", align="center")],
    [CELL("Jabatan kiri", align="center"), CELL("Jabatan kanan", align="center")],
    [CELL("\n\n\n\n", align="center"), CELL("\n\n\n\n", align="center")],
    [CELL([BOLD("Nama kiri")], align="center"), CELL([BOLD("Nama kanan")], align="center")],
    [CELL("NIDN: ...", align="center"), CELL("NRA: ...", align="center")]
  ]
)
""".trimStart(),
    ),
    CodeSnippet(
        "Tembusan",
        """
P("Tembusan:", space_after=2)
P("1. ...", space_after=0)
P("2. Arsip", space_after=0)
""".trimStart(),
    ),
    CodeSnippet(
        "Footer",
        """
HR(style="solid", thickness=1.0, color="000000", space_before=4, space_after=6)
P([ITALIC("\"Motto\"")], align="center", space_after=2)
P("Instagram: @akun", align="center", space_after=4)
HR(style="solid", thickness=1.0, color="000000", space_before=2, space_after=0)
""".trimStart(),
    ),
)

@Composable
fun CodeEditorPane(
    text: String,
    diagnostics: List<String>,
    onTextChange: (String) -> Unit,
    onFormat: () -> Unit,
    onCheck: () -> Unit,
    onOpenAssets: () -> Unit = {},
    onJumpToLine: (Int) -> Unit = {},
    cursorLine: Int = 1,
) {
    var showSnippets by remember { mutableStateOf(false) }
    var field by remember { mutableStateOf(TextFieldValue(text, TextRange(text.length))) }

    LaunchedEffect(text) {
        if (text != field.text) {
            field = TextFieldValue(text, TextRange(text.length))
        }
    }

    Column(Modifier.fillMaxSize()) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp)) {
            TextButton(onClick = onFormat) { Text("Format") }
            TextButton(onClick = onCheck) { Text("Periksa") }
            TextButton(onClick = onOpenAssets) { Text("Aset") }
            TextButton(onClick = { showSnippets = true }) { Text("Snippet") }
            DropdownMenu(expanded = showSnippets, onDismissRequest = { showSnippets = false }) {
                DSX_SNIPPETS.forEach { snip ->
                    DropdownMenuItem(
                        text = { Text(snip.label) },
                        onClick = {
                            showSnippets = false
                            val cur = field.text
                            val next = if (cur.isBlank()) snip.code else cur.trimEnd() + "\n" + snip.code
                            onTextChange(next)
                        },
                    )
                }
            }
        }
        OutlinedTextField(
            value = field,
            onValueChange = {
                field = it
                onTextChange(it.text)
            },
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .padding(horizontal = 8.dp)
                .horizontalScroll(rememberScrollState()),
            textStyle = MaterialTheme.typography.bodySmall.copy(
                fontFamily = FontFamily.Monospace,
                fontSize = 13.sp,
                lineHeight = 18.sp,
            ),
            placeholder = { Text("// document.dsx") },
        )
        if (diagnostics.isNotEmpty()) {
            HorizontalDivider()
            Column(
                Modifier
                    .fillMaxWidth()
                    .padding(8.dp)
                    .verticalScroll(rememberScrollState()),
            ) {
                Text(
                    "Diagnostik (ketuk untuk loncat ke baris)",
                    style = MaterialTheme.typography.labelLarge,
                )
                diagnostics.forEach { d ->
                    val line = Regex("""L(\d+):""").find(d)?.groupValues?.getOrNull(1)?.toIntOrNull()
                    Text(
                        d,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                        modifier = Modifier
                            .padding(vertical = 2.dp)
                            .then(
                                if (line != null) {
                                    Modifier.clickable {
                                        field = jumpTextToLine(field.text, line)
                                        onJumpToLine(line)
                                    }
                                } else {
                                    Modifier
                                },
                            ),
                    )
                }
            }
        }
    }
}

/** Move cursor approximately to a 1-based line number. */
fun jumpTextToLine(text: String, line: Int): TextFieldValue {
    val lines = text.split('\n')
    val idx = (line - 1).coerceIn(0, (lines.size - 1).coerceAtLeast(0))
    var offset = 0
    for (i in 0 until idx) {
        offset += lines[i].length + 1
    }
    return TextFieldValue(text, TextRange(offset, offset))
}
