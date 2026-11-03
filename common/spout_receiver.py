# spout_receiver.py
import SpoutGL
from OpenGL.GL import *
import glfw
import numpy as np
import time


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
        self._receive_texture = None
        self._scaled_framebuffer = None
        self._scaled_texture = None
        self._sender_width = width
        self._sender_height = height

    def stop(self):
        self.should_stop = True
        if self.window:
            glfw.set_window_should_close(self.window, True)

    def _resize_receive_texture(self, new_width, new_height):
        self._sender_width = new_width
        self._sender_height = new_height
        _allocate_texture(self._receive_texture, new_width, new_height)

    def _cleanup_gl(self):
        if self._receive_texture:
            glDeleteTextures(int(self._receive_texture))
            self._receive_texture = None
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
            self.window = glfw.create_window(self.width, self.height, "Spout Receiver", None, None)
            if not self.window:
                raise RuntimeError("Could not create an OpenGL window")
            glfw.make_context_current(self.window)
            glfw.swap_interval(0)
            glViewport(0, 0, self.width, self.height)

            self._receive_texture = glGenTextures(1)
            _allocate_texture(self._receive_texture, self.width, self.height)
            self._scaled_framebuffer, self._scaled_texture = _create_render_target(self.width, self.height)

            setProjection(self.width, self.height)
            glClearColor(0.0, 0.0, 0.0, 1.0)

            with SpoutGL.SpoutReceiver() as receiver:
                receiver.setReceiverName(self.spout_name)
                print(f"Waiting for Spout sender: {self.spout_name}", flush=True)
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
                                glfw.set_window_title(self.window, f"Spout Receiver | {self.actual_fps:.1f} FPS")
                            completed_frames = 0
                            fps_started = t

                        received = receiver.receiveTexture(self._receive_texture, GL_TEXTURE_2D, self.flipped, 0)
                        if not received:
                            if connected:
                                print("Sender disconnected; waiting...", flush=True)
                                connected = False
                            continue
                        if not connected:
                            print(f"Receiving: {self.spout_name}", flush=True)
                            connected = True

                        if receiver.isUpdated():
                            new_width = receiver.getSenderWidth()
                            new_height = receiver.getSenderHeight()
                            if new_width > 0 and new_height > 0 and (
                                new_width != self._sender_width or new_height != self._sender_height
                            ):
                                self._resize_receive_texture(new_width, new_height)
                                buffer = None
                                receiver.receiveTexture(self._receive_texture, GL_TEXTURE_2D, self.flipped, 0)

                        glBindFramebuffer(GL_FRAMEBUFFER, self._scaled_framebuffer)
                        glViewport(0, 0, self.width, self.height)
                        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
                        glActiveTexture(GL_TEXTURE0)
                        glBindTexture(GL_TEXTURE_2D, self._receive_texture)

                        drawFullScreenQuad(self.width, self.height)

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
            raise RuntimeError(f"Spout receiver failed: {e}") from e
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
