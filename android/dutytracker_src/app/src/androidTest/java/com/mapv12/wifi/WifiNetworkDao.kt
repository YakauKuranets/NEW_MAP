package com.mapv12.dutytracker.scanner.wifi

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

@Dao
interface WifiNetworkDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertNetwork(network: WifiNetworkEntity)

    @Query("SELECT * FROM wifi_networks ORDER BY rssi DESC")
    fun getAllNetworks(): Flow<List<WifiNetworkEntity>>

    @Query("SELECT * FROM wifi_networks WHERE ssid LIKE '%' || :query || '%' OR bssid LIKE '%' || :query || '%'")
    suspend fun searchNetworks(query: String): List<WifiNetworkEntity>

    @Query("SELECT COUNT(*) FROM wifi_networks WHERE securityType = 'OPEN' OR securityType = 'WEP'")
    suspend fun getVulnerableNetworksCount(): Int

    @Query("SELECT * FROM wifi_networks WHERE isWpsEnabled = 1")
    suspend fun getWpsEnabledNetworks(): List<WifiNetworkEntity>

    @Query("DELETE FROM wifi_networks WHERE lastSeen < :cutoff")
    suspend fun deleteOldNetworks(cutoff: Long)
}