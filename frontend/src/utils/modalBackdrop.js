import { onMounted, onUnmounted } from 'vue'

export function useBackdropClose() {
  const pressStartedOnBackdrop = Object.create(null)

  function onBackdropMouseDown(key, event) {
    pressStartedOnBackdrop[key] = event.target === event.currentTarget
  }

  function onBackdropMouseUp(key, event) {
    const startedOnBackdrop = Boolean(pressStartedOnBackdrop[key])
    const endedOnBackdrop = event.target === event.currentTarget
    pressStartedOnBackdrop[key] = false

    return startedOnBackdrop && endedOnBackdrop
  }

  function resetBackdropPressState() {
    Object.keys(pressStartedOnBackdrop).forEach((key) => {
      pressStartedOnBackdrop[key] = false
    })
  }

  onMounted(() => {
    window.addEventListener('mouseup', resetBackdropPressState, true)
  })

  onUnmounted(() => {
    window.removeEventListener('mouseup', resetBackdropPressState, true)
  })

  return {
    onBackdropMouseDown,
    onBackdropMouseUp
  }
}
