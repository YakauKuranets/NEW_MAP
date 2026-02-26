package com.mapv12.dutytracker.scanner.wifi

import android.content.Context
import android.net.wifi.ScanResult
import android.net.wifi.WifiManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.NetworkInterface
import java.util.*

class WifiSecurityAnalyzer(private val context: Context) {

    private val wifiManager = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager

    data class SecurityAnalysisResult(
        val ssid: String,
        val bssid: String,
        val securityType: String,
        val signalStrength: Int,          // dBm
        val signalPercentage: Int,         // 0-100%
        val channel: Int,
        val frequency: Int,
        val isWpsSupported: Boolean,        // Проверка поддержки WPS
        val wpsVulnerable: Boolean,          // Подозрение на уязвимость (WPS включен)
        val distanceEstimate: Double,        // Оценка расстояния (метры)
        val manufacturer: String?,
        val channelCongestion: String        // "Low", "Medium", "High"
    )

    /**
     * Сканирует доступные сети и возвращает подробный анализ
     */
    suspend fun analyzeNetworks(): List<SecurityAnalysisResult> = withContext(Dispatchers.IO) {
        val success = wifiManager.startScan()
        if (!success) return@withContext emptyList()

        Thread.sleep(2000) // Ждём результаты сканирования

        val scanResults = wifiManager.scanResults
        val currentBand = getCurrentBand()

        scanResults.map { result ->
            val securityType = parseSecurityType(result.capabilities)
            val channel = convertFrequencyToChannel(result.frequency)
            val wpsInfo = checkWpsSupport(result.capabilities)

            SecurityAnalysisResult(
                ssid = result.ssid.ifEmpty { "<Hidden Network>" },
                bssid = result.bssid,
                securityType = securityType,
                signalStrength = result.level,
                signalPercentage = calculateSignalPercentage(result.level),
                channel = channel,
                frequency = result.frequency,
                isWpsSupported = wpsInfo.first,
                wpsVulnerable = wpsInfo.first && securityType in listOf("WPA", "WPA2"),
                distanceEstimate = estimateDistance(result.level, result.frequency),
                manufacturer = getManufacturerFromBssid(result.bssid),
                channelCongestion = analyzeChannelCongestion(scanResults, channel)
            )
        }.sortedByDescending { it.signalStrength }
    }

    /**
     * Определяет тип безопасности по строке capabilities [citation:2]
     */
    private fun parseSecurityType(capabilities: String): String {
        return when {
            capabilities.contains("WPA3") -> "WPA3"
            capabilities.contains("WPA2") -> "WPA2"
            capabilities.contains("WPA") -> "WPA"
            capabilities.contains("WEP") -> "WEP"
            capabilities.contains("OPEN") && !capabilities.contains("WPS") -> "OPEN"
            else -> "UNKNOWN"
        }
    }

    /**
     * Проверяет поддержку WPS по строке capabilities
     */
    private fun checkWpsSupport(capabilities: String): Pair<Boolean, String?> {
        val hasWps = capabilities.contains("WPS", ignoreCase = true)
        val wpsType = when {
            capabilities.contains("WPS-PIN", ignoreCase = true) -> "PIN"
            capabilities.contains("WPS-PBC", ignoreCase = true) -> "PBC"
            hasWps -> "GENERIC"
            else -> null
        }
        return Pair(hasWps, wpsType)
    }

    /**
     * Конвертирует частоту в номер канала [citation:2]
     */
    private fun convertFrequencyToChannel(frequency: Int): Int {
        return when (frequency) {
            in 2412..2484 -> (frequency - 2412) / 5 + 1
            in 5170..5825 -> (frequency - 5170) / 5 + 34
            else -> 0
        }
    }

    /**
     * Преобразует RSSI в процентное значение [citation:2]
     */
    private fun calculateSignalPercentage(rssi: Int): Int {
        val minRssi = -100
        val maxRssi = -50
        return ((rssi - minRssi) * 100 / (maxRssi - minRssi)).coerceIn(0, 100)
    }

    /**
     * Оценивает расстояние до точки доступа [citation:2]
     */
    private fun estimateDistance(rssi: Int, frequency: Int): Double {
        val ratio = (27.55 - (20 * Math.log10(frequency.toDouble())) + Math.abs(rssi)) / 20.0
        return Math.pow(10.0, ratio)
    }

    /**
     * Анализирует загруженность канала [citation:6]
     */
    private fun analyzeChannelCongestion(scanResults: List<ScanResult>, channel: Int): String {
        val count = scanResults.count { convertFrequencyToChannel(it.frequency) == channel }
        return when {
            count < 3 -> "Low"
            count < 6 -> "Medium"
            else -> "High"
        }
    }

    /**
     * Получает производителя по MAC-адресу (первые 3 октета)
     */
    private fun getManufacturerFromBssid(bssid: String): String? {
        val oui = bssid.replace(":", "").substring(0, 6).uppercase()
        // Здесь можно добавить базу OUI
        return when (oui.substring(0, 3)) {
            "00:1" -> "Cisco"
            "00:2" -> "TP-Link"
            "00:3" -> "D-Link"
            "00:4" -> "Netgear"
            "00:5" -> "Huawei"
            else -> null
        }
    }

    private fun getCurrentBand(): String {
        val wifiInfo = wifiManager.connectionInfo
        return if (wifiInfo.frequency > 5000) "5 GHz" else "2.4 GHz"
    }
}