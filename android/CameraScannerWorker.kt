package com.mapv12.dutytracker.scanner

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.mapv12.dutytracker.data.AppDatabase
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class CameraScannerWorker(
    context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        try {
            val scanner = CameraScanner(applicationContext)
            val foundCameras = scanner.scanNetwork(timeoutMs = 4000)

            val db = AppDatabase.getInstance(applicationContext)
            val cameraDao = db.cameraDao()

            foundCameras.forEach { cam ->
                val existing = cameraDao.getCameraByIp(cam.ip)
                if (existing == null) {
                    val entity = CameraEntity(
                        ip = cam.ip,
                        port = cam.port,
                        vendor = cam.vendor,
                        onvifUrl = cam.onvifUrl,
                        authType = cam.authType,
                        firstSeen = System.currentTimeMillis(),
                        lastSeen = System.currentTimeMillis()
                    )
                    cameraDao.insertCamera(entity)
                } else {
                    val updated = existing.copy(
                        port = cam.port,
                        vendor = cam.vendor ?: existing.vendor,
                        onvifUrl = cam.onvifUrl ?: existing.onvifUrl,
                        authType = cam.authType ?: existing.authType,
                        lastSeen = System.currentTimeMillis()
                    )
                    cameraDao.insertCamera(updated)
                }
            }

            val weekAgo = System.currentTimeMillis() - 7 * 24 * 60 * 60 * 1000
            cameraDao.deleteOldCameras(weekAgo)

            Result.success()
        } catch (e: Exception) {
            e.printStackTrace()
            Result.retry()
        }
    }
}
