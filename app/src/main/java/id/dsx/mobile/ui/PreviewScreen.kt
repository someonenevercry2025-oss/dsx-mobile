package id.dsx.mobile.ui

import android.annotation.SuppressLint
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import java.io.File

@SuppressLint("SetJavaScriptEnabled")
@Composable
fun HtmlPreviewPane(
    htmlFile: File?,
    htmlContent: String? = null,
) {
    Column(Modifier.fillMaxSize()) {
        Box(
            Modifier
                .fillMaxWidth()
                .background(MaterialTheme.colorScheme.primaryContainer)
                .padding(horizontal = 12.dp, vertical = 6.dp),
        ) {
            Text(
                "Pratinjau perkiraan, hasil Word bisa sedikit berbeda",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onPrimaryContainer,
            )
        }
        AndroidView(
            factory = { ctx ->
                WebView(ctx).apply {
                    webViewClient = WebViewClient()
                    settings.javaScriptEnabled = false
                    settings.allowFileAccess = true
                    settings.builtInZoomControls = true
                    settings.displayZoomControls = false
                    settings.useWideViewPort = true
                    settings.loadWithOverviewMode = true
                }
            },
            update = { webView ->
                when {
                    htmlFile != null && htmlFile.exists() ->
                        webView.loadUrl("file://${htmlFile.absolutePath}")
                    !htmlContent.isNullOrBlank() ->
                        webView.loadDataWithBaseURL(
                            null,
                            htmlContent,
                            "text/html",
                            "UTF-8",
                            null,
                        )
                    else ->
                        webView.loadData(
                            "<p style='padding:16px;font-family:sans-serif;color:#666'>Belum ada pratinjau. Bangun HTML terlebih dahulu.</p>",
                            "text/html",
                            "UTF-8",
                        )
                }
            },
            modifier = Modifier.fillMaxSize(),
        )
    }
}
