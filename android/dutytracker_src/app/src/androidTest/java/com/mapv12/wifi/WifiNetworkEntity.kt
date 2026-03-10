package com.mapv12.dutytracker.scanner.wifi

import androidx.room.Entity
import androidx.room.PrimaryKey
import java.util.Date

@Entity(tableName = "wifi_networks")
data class WifiNetworkEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val ssid: String,                    // Имя сети
    val bssid: String,                    // MAC-адрес точки доступа
    val capabilities: String,              // Строка с возможностями безопасности
    val frequency: Int,                    // Частота в МГц
    val rssi: Int,                         // Уровень сигнала в dBm
    val securityType: String,               // OPEN, WEP, WPA, WPA2, WPA3
    val channel: Int,                       // Номер канала
    val isWpsEnabled: Boolean = false,       // Доступен ли WPS (для диагностики)
    val manufacturer: String? = null,        // Производитель по BSSID
    val firstSeen: Long = System.currentTimeMillis(),
    val lastSeen: Long = System.currentTimeMillis()
)