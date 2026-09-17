package com.cabina360.operator

import android.app.Application
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class Cabina360Application : Application() {
    val container by lazy { AppContainer(applicationContext) }

    override fun onCreate() {
        super.onCreate()
        CoroutineScope(SupervisorJob() + Dispatchers.IO).launch {
            container.captureRepository.reconcile()
            container.syncRepository.pendingProcessing().forEach { container.syncCoordinator.enqueueProcessing(it.id) }
            container.syncRepository.pendingUploads().forEach { container.syncCoordinator.enqueueUpload(it.id) }
            container.syncCoordinator.scheduleCleanup()
        }
    }
}
