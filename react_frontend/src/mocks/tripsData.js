export const tripsData = [
  {
    vendor: 'Agent-01',
    path: [
      [27.520, 53.880],
      [27.545, 53.892],
      [27.560, 53.905],
      [27.585, 53.913],
      [27.615, 53.926],
    ],
    timestamps: [1710000000, 1710000120, 1710000240, 1710000360, 1710000480],
  },
  {
    vendor: 'Agent-02',
    path: [
      [27.505, 53.915],
      [27.535, 53.928],
      [27.565, 53.939],
      [27.592, 53.949],
      [27.622, 53.958],
    ],
    timestamps: [1710000000, 1710000100, 1710000220, 1710000340, 1710000460],
  },
];

const allTimestamps = tripsData.flatMap((trip) => trip.timestamps || []);

export const timelineMinTime = allTimestamps.length ? Math.min(...allTimestamps) : 0;
export const timelineMaxTime = allTimestamps.length ? Math.max(...allTimestamps) : 0;
