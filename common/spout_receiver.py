# spout_receiver.py
# Windows は Spout、macOS は Syphon で TD の映像を受信する。
import sys
from OpenGL.GL import *
import glfw
import numpy as np
import time

if sys.platform == "darwin":
    import syphon
else:
    import SpoutGL


def _allocate_texture(texture_id, width, height):
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)
    glBindTexture(GL_TEXTURE_2D, 0)


def _create_render_target(width, height):
    texture = glGenTextures(1)
    _allocate_texture(texture, width, height)

    framebuffer = glGenFramebuffers(1)
    glBindFramebuffer(GL_FRAMEBUFFER, framebuffer)
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, texture, 0)
    status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
    if status != GL_FRAMEBUFFER_COMPLETE:
        raise RuntimeError("Failed to create framebuffer for scaled output")
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    return framebuffer, texture


def setProjection(width, height):
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    glOrtho(0, width, height, 0, 1, -1)
    glMatrixMode(GL_MODELVIEW)

def drawFullScreenQuad(width, height):
    glEnable(GL_TEXTURE_2D)
    glBegin(GL_QUADS)
    glTexCoord(0, 0)
    glVertex2f(0, 0)
    glTexCoord(1, 0)
    glVertex2f(width, 0)
    glTexCoord(1, 1)
    glVertex2f(width, height)
    glTexCoord(0, 1)
    glVertex2f(0, height)
    glEnd()
    glDisable(GL_TEXTURE_2D)

class _SpoutSource:
    label = "Spout sender"
    title = "Spout Receiver"

    def __init__(self, name, width, height, flipped):
        self.name = name
        self.flipped = flipped
        self._context = SpoutGL.SpoutReceiver()
        self._receiver = self._context.__enter__()
        self._receiver.setReceiverName(name)
        self._texture = glGenTextures(1)
        self._width = width
        self._height = height
        _allocate_texture(self._texture, width, height)

    def receive(self):
        received = self._receiver.receiveTexture(self._texture, GL_TEXTURE_2D, self.flipped, 0)
        if not received:
            return False
        if self._receiver.isUpdated():
            new_width = self._receiver.getSenderWidth()
            new_height = self._receiver.getSenderHeight()
            if new_width > 0 and new_height > 0 and (new_width != self._width or new_height != self._height):
                self._width = new_width
                self._height = new_height
                _allocate_texture(self._texture, new_width, new_height)
                self._receiver.receiveTexture(self._texture, GL_TEXTURE_2D, self.flipped, 0)
        return True

    def draw(self, width, height):
        glBindTexture(GL_TEXTURE_2D, self._texture)
        drawFullScreenQuad(width, height)

    def close(self):
        try:
            self._context.__exit__(None, None, None)
        finally:
            glDeleteTextures(int(self._texture))


class _SyphonSource:
    label = "Syphon server"
    title = "Syphon Receiver"
    LOOKUP_INTERVAL = 0.5

    def __init__(self, name, width, height, flipped):
        self.name = name
        self.flipped = flipped
        self._directory = syphon.SyphonServerDirectory()
        self._directory.run_loop_interval = 0.01
        self._client = None
        self._image = None
        self._next_lookup = 0.0

    def receive(self):
        if self._client is not None and not self._client.is_valid:
            self._disconnect()
        if self._client is None:
            now = time.perf_counter()
            if now < self._next_lookup:
                return False
            self._next_lookup = now + self.LOOKUP_INTERVAL
            servers = self._directory.servers_matching_name(name=self.name)
            if not servers:
                return False
            self._client = syphon.SyphonOpenGLClient(servers[0])
        if self._client.has_new_frame:
            self._image = self._client.new_frame_image
        return self._image is not None

    def draw(self, width, height):
        # Syphon は GL_TEXTURE_RECTANGLE（ピクセル単位の座標、下が原点）で届く。
        # flipped=True で Spout の flipped=True と同じ向きになるように描く。
        size = self._image.textureSize()
        tw, th = size.width, size.height
        top, bottom = (0, th) if self.flipped else (th, 0)
        glEnable(GL_TEXTURE_RECTANGLE)
        glBindTexture(GL_TEXTURE_RECTANGLE, self._image.textureName())
        glTexParameteri(GL_TEXTURE_RECTANGLE, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_RECTANGLE, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glBegin(GL_QUADS)
        glTexCoord(0, top)
        glVertex2f(0, 0)
        glTexCoord(tw, top)
        glVertex2f(width, 0)
        glTexCoord(tw, bottom)
        glVertex2f(width, height)
        glTexCoord(0, bottom)
        glVertex2f(0, height)
        glEnd()
        glBindTexture(GL_TEXTURE_RECTANGLE, 0)
        glDisable(GL_TEXTURE_RECTANGLE)

    def _disconnect(self):
        self._image = None
        self._client.stop()
        self._client = None

    def close(self):
        if self._client is not None:
            self._disconnect()
        self._directory.close()


_Source = _SyphonSource if sys.platform == "darwin" else _SpoutSource


class SpoutReceiver:
    def __init__(self, spout_name: str, width: int, height: int, fps: int, show_window: bool = False, flipped: bool = False):
        self.spout_name = spout_name
        self.width = width
        self.height = height
        self.fps = fps
        self.show_window = show_window
        self.flipped = flipped
        self.window = None
        self.should_stop = False

        self.actual_fps = 0
        self._source = None
        self._scaled_framebuffer = None
        self._scaled_texture = None

    def stop(self):
        self.should_stop = True
        if self.window:
            glfw.set_window_should_close(self.window, True)

    def _cleanup_gl(self):
        if self._source:
            self._source.close()
            self._source = None
        if self._scaled_texture:
            glDeleteTextures(int(self._scaled_texture))
            self._scaled_texture = None
        if self._scaled_framebuffer:
            glDeleteFramebuffers(1, [int(self._scaled_framebuffer)])
            self._scaled_framebuffer = None

    def start(self, callback=None):
        try:
            if not glfw.init():
                raise RuntimeError("GLFW initialization failed")
            glfw.window_hint(glfw.VISIBLE, glfw.TRUE if self.show_window else glfw.FALSE)
            glfw.window_hint(glfw.REFRESH_RATE, int(self.fps))
            if sys.platform == "darwin":
                # Retina でもウィンドウの画素数を width×height にそろえる。
                glfw.window_hint(glfw.COCOA_RETINA_FRAMEBUFFER, glfw.FALSE)
            self.window = glfw.create_window(self.width, self.height, _Source.title, None, None)
            if not self.window:
                raise RuntimeError("Could not create an OpenGL window")
            glfw.make_context_current(self.window)
            glfw.swap_interval(0)
            glViewport(0, 0, self.width, self.height)

            self._source = _Source(self.spout_name, self.width, self.height, self.flipped)
            self._scaled_framebuffer, self._scaled_texture = _create_render_target(self.width, self.height)

            setProjection(self.width, self.height)
            glClearColor(0.0, 0.0, 0.0, 1.0)

            source = self._source
            print(f"Waiting for {source.label}: {self.spout_name}", flush=True)
            connected = False
            buffer = None
            latest_time = time.perf_counter()
            fps_started = latest_time
            completed_frames = 0

            while not glfw.window_should_close(self.window) and not self.should_stop:
                try:
                    glfw.poll_events()
                    if glfw.get_key(self.window, glfw.KEY_ESCAPE) == glfw.PRESS:
                        break

                    t = time.perf_counter()
                    sleep_time = 1 / self.fps - (t - latest_time)
                    if sleep_time > 0:
                        time.sleep(min(sleep_time, 0.1))  # 最大0.1秒でスリープを制限
                        continue
                    latest_time = t
                    elapsed = t - fps_started
                    if elapsed >= 0.5:
                        self.actual_fps = completed_frames / elapsed
                        if self.show_window:
                            glfw.set_window_title(self.window, f"{source.title} | {self.actual_fps:.1f} FPS")
                        completed_frames = 0
                        fps_started = t

                    if not source.receive():
                        if connected:
                            print("Sender disconnected; waiting...", flush=True)
                            connected = False
                        continue
                    if not connected:
                        print(f"Receiving: {self.spout_name}", flush=True)
                        connected = True

                    glBindFramebuffer(GL_FRAMEBUFFER, self._scaled_framebuffer)
                    glViewport(0, 0, self.width, self.height)
                    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
                    glActiveTexture(GL_TEXTURE0)
                    source.draw(self.width, self.height)

                    if callback:
                        if buffer is None:
                            buffer = (GLubyte * (self.width * self.height * 3))()
                        glPixelStorei(GL_PACK_ALIGNMENT, 1)
                        glReadPixels(0, 0, self.width, self.height, GL_RGB, GL_UNSIGNED_BYTE, buffer)
                        arr = np.array(buffer, dtype=np.uint8).reshape((self.height, self.width, 3))

                    glBindFramebuffer(GL_FRAMEBUFFER, 0)

                    if self.show_window:
                        glViewport(0, 0, self.width, self.height)
                        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
                        glActiveTexture(GL_TEXTURE0)
                        glBindTexture(GL_TEXTURE_2D, self._scaled_texture)
                        drawFullScreenQuad(self.width, self.height)
                        glfw.swap_buffers(self.window)

                    if callback and not self.should_stop:
                        result = callback(arr)
                        if result is False:
                            break
                    completed_frames += 1

                except KeyboardInterrupt:
                    break
                except Exception as e:
                    raise RuntimeError(f"Receiver error: {e}") from e

        except Exception as e:
            raise RuntimeError(f"{_Source.title.capitalize()} failed: {e}") from e
        finally:
            try:
                if self.window:
                    glfw.make_context_current(self.window)
                    try:
                        self._cleanup_gl()
                    finally:
                        glfw.destroy_window(self.window)
                        self.window = None
            finally:
                glfw.terminate()
            print("Receiver stopped")
