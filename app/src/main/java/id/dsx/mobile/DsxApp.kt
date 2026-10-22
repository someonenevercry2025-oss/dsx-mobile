package id.dsx.mobile

import android.app.Application
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import id.dsx.mobile.bridge.PythonBridge
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class DsxApp : Application() {

    private val appScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    @Volatile
    var pythonReady: Boolean = false
        private set

    @Volatile
    var pythonError: String? = null
        private set

    override fun onCreate() {
        super.onCreate()
        appScope.launch {
            try {
                if (!Python.isStarted()) {
                    Python.start(AndroidPlatform(this@DsxApp))
                }
                PythonBridge.init()
                // Warm-up
                PythonBridge.version()
                pythonReady = true
            } catch (e: Exception) {
                pythonError = e.message ?: e.toString()
            }
        }
    }
}
