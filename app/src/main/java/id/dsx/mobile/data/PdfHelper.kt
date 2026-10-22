package id.dsx.mobile.data

import android.content.Context
import android.print.PrintAttributes
import android.print.PrintManager
import android.webkit.WebView
import android.webkit.WebViewClient
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream

/**
 * PDF sederhana dari HTML engine (bukan LibreOffice).
 * Tata letak mengikuti HTML; hasil Word/DOCX tetap acuan utama.
 */
object PdfHelper {

    @Volatile
    private var printWebView: WebView? = null

    /**
     * Tampilkan sistem print dialog agar pengguna bisa "Save as PDF".
     * Ini cara paling andal di Android tanpa dependensi native PDF.
     */
    fun printHtml(
        context: Context,
        htmlFile: File,
        jobName: String = "DSX Dokumen",
    ) {
        val webView = WebView(context.applicationContext)
        printWebView = webView
        webView.settings.javaScriptEnabled = false
        webView.settings.allowFileAccess = true
        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView, url: String?) {
                val adapter = view.createPrintDocumentAdapter(jobName)
                val printManager = context.getSystemService(Context.PRINT_SERVICE) as PrintManager
                val attrs = PrintAttributes.Builder()
                    .setMediaSize(PrintAttributes.MediaSize.ISO_A4)
                    .setResolution(PrintAttributes.Resolution("pdf", "pdf", 300, 300))
                    .setMinMargins(PrintAttributes.Margins.NO_MARGINS)
                    .build()
                printManager.print(jobName, adapter, attrs)
                printWebView = null
            }
        }
        webView.loadUrl("file://${htmlFile.absolutePath}")
    }

    fun copyTo(src: File, dest: File) {
        FileInputStream(src).use { input ->
            FileOutputStream(dest).use { output ->
                input.copyTo(output)
            }
        }
    }
}
