set(COMPONENT_SRCDIRS
    "src"
)

set(COMPONENT_ADD_INCLUDEDIRS
    "src"
)

# Set PSYCHIC_ARDUINO=ON when building with the arduino-esp32 component.
# For pure ESP-IDF builds (no Arduino framework), leave it OFF (the default).
option(PSYCHIC_ARDUINO "Build with Arduino framework support" OFF)

if(PSYCHIC_ARDUINO)
    set(COMPONENT_REQUIRES
        "arduino-esp32"
        "esp_https_server"
        "esp_http_server"
        "mbedtls"
        "arduinojson"
    )
else()
    set(COMPONENT_REQUIRES
        "esp_https_server"
        "esp_http_server"
        "mbedtls"
        "arduinojson"
    )
endif()

register_component()

target_compile_definitions(${COMPONENT_TARGET} PUBLIC -DESP32)
target_compile_options(${COMPONENT_TARGET} PRIVATE -fno-rtti)
