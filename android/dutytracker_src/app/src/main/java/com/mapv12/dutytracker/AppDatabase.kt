package com.mapv12.dutytracker

import androidx.room.Database
import androidx.room.RoomDatabase
import com.mapv12.dutytracker.scanner.CameraDao
import com.mapv12.dutytracker.scanner.CameraEntity

@Database(
    entities = [
        TrackPointEntity::class,
        EventJournalEntity::class,
        ChatMessageEntity::class,
        CameraEntity::class
    ],
    version = 6,               // увеличь версию с 5 до 6
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun trackPointDao(): TrackPointDao
    abstract fun eventJournalDao(): EventJournalDao
    abstract fun chatMessageDao(): ChatMessageDao
    abstract fun cameraDao(): CameraDao   // новый DAO
}
