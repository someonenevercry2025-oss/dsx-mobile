package id.dsx.mobile.data

import android.content.Context
import android.os.Bundle
import android.os.CancellationSignal
import android.os.ParcelFileDescriptor
import android.print.PageRange
import android.print.PrintAttributes
import android.print.PrintDocumentAdapter
import android.print.PrintDocumentInfo
import android.print.PrintManager
import android.webkit.WebView
import android.webkit.WebViewClient
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import kotlin.coroutines.resume
import kotlin.coroutines.suspendCoroutine

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

    /**
     * Render HTML ke berkas PDF di background menggunakan PrintDocumentAdapter
     * tanpa UI dialog (best-effort; beberapa OEM memerlukan dialog).
     */
    suspend fun renderHtmlToPdf(
        context: Context,
        htmlFile: File,
        outputPdf: File,
        jobName: String = "DSX",
    ): Result<File> = suspendCoroutine { cont ->
        try {
            val webView = WebView(context.applicationContext)
            webView.settings.javaScriptEnabled = false
        webView.settings.allowFileAccess = true
            webView.webViewClient = object : WebViewClient() {
                override fun onPageFinished(view: WebView, url: String?) {
                    try {
                        val adapter = view.createPrintDocumentAdapter(jobName)
                        val attrs = PrintAttributes.Builder()
                            .setMediaSize(PrintAttributes.MediaSize.ISO_A4)
                            .setResolution(PrintAttributes.Resolution("pdf", "pdf", 300, 300))
                            .setMinMargins(PrintAttributes.Margins.NO_MARGINS)
                            .build()

                        // Layout
                        adapter.onLayout(
                            null,
                            attrs,
                            CancellationSignal(),
                            object : PrintDocumentAdapter.LayoutResultCallback() {
                                override fun onLayoutFinished(info: PrintDocumentInfo, changed: Boolean) {
                                    // Write pages
                                    if (outputPdf.exists()) outputPdf.delete()
                                    val pfd = ParcelFileDescriptor.open(
                                        outputPdf,
                                        ParcelFileDescriptor.MODE_READ_WRITE or
                                            ParcelFileDescriptor.MODE_CREATE or
                                            ParcelFileDescriptor.MODE_TRUNCATE,
                                    )
                                    adapter.onWrite(
                                        arrayOf(PageRange.ALL_PAGES),
                                        pfd,
                                        CancellationSignal(),
                                        object : PrintDocumentAdapter.WriteResultCallback() {
                                            override fun onWriteFinished(pages: Array<out PageRange>) {
                                                try {
                                                    pfd.close()
                                                } catch (_: Exception) {
                                                }
                                                if (outputPdf.exists() && outputPdf.length() > 0) {
                                                    cont.resume(Result.success(outputPdf))
                                                } else {
                                                    cont.resume(
                                                        Result.failure(
                                                            Exception(
                                                                "PDF kosong. Gunakan 'Cetak / Simpan PDF' " +
                                                                    "dari dialog sistem.",
                                                            ),
                                                        ),
                                                    )
                                                }
                                            }

                                            override fun onWriteFailed(error: CharSequence?) {
                                                try {
                                                    pfd.close()
                                                } catch (_: Exception) {
                                                }
                                                cont.resume(
                                                    Result.failure(
                                                        Exception(error?.toString() ?: "Gagal menulis PDF"),
                                                    ),
                                                )
                                            }
                                        },
                                    )
                                }

                                override fun onLayoutFailed(error: CharSequence?) {
                                    cont.resume(
                                        Result.failure(
                                            Exception(error?.toString() ?: "Gagal layout PDF"),
                                        ),
                                    )
                                }
                            },
                            Bundle(),
                        )
                    } catch (e: Exception) {
                        cont.resume(Result.failure(e))
                    }
                }
            }
            webView.loadUrl("file://${htmlFile.absolutePath}")
        } catch (e: Exception) {
            cont.resume(Result.failure(e))
        }
    }

    fun copyTo(src: File, dest: File) {
        FileInputStream(src).use { input ->
            FileOutputStream(dest).use { output ->
                input.copyTo(output)
            }
        }
    }
}
