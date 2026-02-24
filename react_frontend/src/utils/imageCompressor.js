import imageCompression from 'browser-image-compression';

const COMPRESSION_OPTIONS = {
  maxSizeMB: 0.5,
  maxWidthOrHeight: 1280,
  useWebWorker: true,
};

/**
 * Compresses an image file for field-friendly traffic usage.
 * @param {File} file
 * @returns {Promise<File>}
 */
export async function compressImage(file) {
  if (!(file instanceof File)) {
    throw new Error('invalid_image_file');
  }

  return imageCompression(file, COMPRESSION_OPTIONS);
}

export default compressImage;
