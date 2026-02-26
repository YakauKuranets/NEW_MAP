@Database(
    entities = [
        TrackPointEntity::class,
        EventJournalEntity::class,
        ChatMessageEntity::class,
        CameraEntity::class   // добавлено
    ],
    version = 6,   // увеличиваем версию
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun trackPointDao(): TrackPointDao
    abstract fun eventJournalDao(): EventJournalDao
    abstract fun chatMessageDao(): ChatMessageDao
    abstract fun cameraDao(): CameraDao   // новый DAO
}
