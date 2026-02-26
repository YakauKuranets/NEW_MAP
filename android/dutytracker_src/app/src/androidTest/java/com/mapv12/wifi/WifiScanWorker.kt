package com.mapv12.dutytracker.scanner.wifi

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.mapv12.dutytracker.data.AppDatabase
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class WifiScanWorker(
    context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        try {
            val analyzer = WifiSecurityAnalyzer(applicationContext)
            val networks = analyzer.analyzeNetworks()

            val db = AppDatabase.getInstance(applicationContext)
            val wifiDao = db.wifiNetworkDao()

            networks.forEach { net ->
                val entity = WifiNetworkEntity(
                    ssid = net.ssid,
                    bssid = net.bssid,
                    capabilities = net.securityType,
                    frequency = net.frequency,
                    rssi = net.signalStrength,
                    securityType = net.securityType,
                    channel = net.channel,
                    isWpsEnabled = net.isWpsSupported,
                    manufacturer = net.manufacturer,
                    lastSeen = System.currentTimeMillis()
                )
                wifiDao.insertNetwork(entity)
            }

            // Удаляем сети, не видевшиеся более 24 часов
            val dayAgo = System.currentTimeMillis() - 24 * 60 * 60 * 1000
            wifiDao.deleteOldNetworks(dayAgo)

            Result.success()
        } catch (e: Exception) {
            e.printStackTrace()
            Result.retry()
        }
    }
}