#include <stdio.h>
#include <string.h>
#include <inttypes.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/spi_master.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_task_wdt.h"

static const char *TAG = "SPI_DUMPER";

// SPI pins (adjust to match your wiring)
#define PIN_NUM_MISO 19
#define PIN_NUM_MOSI 23
#define PIN_NUM_CLK  18
#define PIN_NUM_CS   5

// SPI commands for standard flash chips
#define CMD_READ_JEDEC_ID 0x9F
#define CMD_READ_DATA     0x03

static spi_device_handle_t spi;

void init_spi() {
    esp_err_t ret;

    spi_bus_config_t buscfg = {
        .miso_io_num = PIN_NUM_MISO,
        .mosi_io_num = PIN_NUM_MOSI,
        .sclk_io_num = PIN_NUM_CLK,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = 4096
    };

    spi_device_interface_config_t devcfg = {
        .clock_speed_hz = 10000000,  // 10MHz - suitable for most chips (check datasheet)
        .mode = 0,                   // SPI mode 0
        .spics_io_num = PIN_NUM_CS,
        .queue_size = 7,
    };

    ret = spi_bus_initialize(SPI2_HOST, &buscfg, SPI_DMA_CH_AUTO);
    ESP_ERROR_CHECK(ret);
    ret = spi_bus_add_device(SPI2_HOST, &devcfg, &spi);
    ESP_ERROR_CHECK(ret);

    printf("SPI_READY\n");
    ESP_LOGI(TAG, "SPI initialized");
}

void read_chip_id() {
    esp_err_t ret;
    spi_transaction_t t;
    uint8_t tx_data[4] = {CMD_READ_JEDEC_ID, 0xFF, 0xFF, 0xFF};  // Command + 3 dummies
    uint8_t rx_data[4] = {0};

    memset(&t, 0, sizeof(t));
    t.length = 32;  // 4 bytes * 8 bits
    t.tx_buffer = tx_data;
    t.rx_buffer = rx_data;

    ret = spi_device_polling_transmit(spi, &t);
    if (ret != ESP_OK) {
        printf("ERROR: Failed to read JEDEC ID\n");
        return;
    }

    // Extract ID from rx_data[1..3] (rx_data[0] is garbage)
    uint8_t id_data[3] = {rx_data[1], rx_data[2], rx_data[3]};

    printf("CHIP_ID: %02X %02X %02X\n", id_data[0], id_data[1], id_data[2]);

    // Decode common chip types (expanded)
    const char *chip_type = "Unknown";
    if (id_data[0] == 0xEF) {
        chip_type = "Winbond W25Q series";
    } else if (id_data[0] == 0xC2) {
        chip_type = "Macronix MX25L series";
    } else if (id_data[0] == 0x1F) {
        chip_type = "Atmel/Adesto AT25 series";
    } else if (id_data[0] == 0xC8) {
        chip_type = "GigaDevice GD25Q series";
    } else if (id_data[0] == 0x20) {
        chip_type = "Micron MT25Q series";
    } else if (id_data[0] == 0x01) {
        chip_type = "Spansion/Cypress S25FL series";
    }
    printf("CHIP_TYPE: %s\n", chip_type);

    // Estimate size from device ID (expanded for common sizes)
    uint32_t size = 0;
    switch (id_data[2]) {
        case 0x13: size = 512 * 1024; break;      // 512KB
        case 0x14: size = 1024 * 1024; break;     // 1MB
        case 0x15: size = 2 * 1024 * 1024; break; // 2MB
        case 0x16: size = 4 * 1024 * 1024; break; // 4MB
        case 0x17: size = 8 * 1024 * 1024; break; // 8MB
        case 0x18: size = 16 * 1024 * 1024; break; // 16MB
        case 0x19: size = 32 * 1024 * 1024; break; // 32MB
        case 0x20: size = 64 * 1024 * 1024; break; // 64MB
        case 0x21: size = 128 * 1024 * 1024; break; // 128MB
    }

    if (size > 0) {
        printf("CHIP_SIZE: %" PRIu32 " bytes (%" PRIu32 "MB)\n", size, size / (1024 * 1024));
    } else {
        printf("CHIP_SIZE: Unknown\n");
    }
}

void read_block(uint32_t addr, uint32_t size) {
    esp_err_t ret;
    if (size > 256) size = 256; // Limit to 256 bytes per call

    uint8_t tx_data[4 + 256];
    uint8_t rx_data[4 + 256];

    // Prepare tx: command + 24-bit address + dummies for data phase
    tx_data[0] = CMD_READ_DATA;
    tx_data[1] = (addr >> 16) & 0xFF;
    tx_data[2] = (addr >> 8) & 0xFF;
    tx_data[3] = addr & 0xFF;
    for (uint32_t i = 4; i < 4 + size; i++) {
        tx_data[i] = 0xFF;  // Dummies for clocking out data
    }

    spi_transaction_t t;
    memset(&t, 0, sizeof(t));
    t.length = (4 + size) * 8;
    t.tx_buffer = tx_data;
    t.rx_buffer = rx_data;

    ret = spi_device_polling_transmit(spi, &t);
    if (ret != ESP_OK) {
        printf("ERROR: Failed to read data from 0x%08" PRIX32 "\n", addr);
        return;
    }

    // Extract data from rx_data[4..4+size-1] (first 4 bytes are garbage)
    uint8_t read_buffer[256];
    memcpy(read_buffer, rx_data + 4, size);

    // Output as hex with spaces for readability
    printf("DATA: %08" PRIX32 " ", addr);
    for (uint32_t i = 0; i < size; i++) {
        printf("%02X ", read_buffer[i]);
    }
    printf("\n");
}

void dump_flash(uint32_t start_addr, uint32_t size) {
    printf("DUMP_START: %08" PRIX32 " %08" PRIX32 "\n", start_addr, size);

    uint32_t addr = start_addr;
    uint32_t remaining = size;

    while (remaining > 0) {
        uint32_t chunk_size = (remaining > 256) ? 256 : remaining;
        read_block(addr, chunk_size);

        addr += chunk_size;
        remaining -= chunk_size;

        // Small delay to allow other tasks/serial processing
        vTaskDelay(1 / portTICK_PERIOD_MS);
    }

    printf("DUMP_END\n");
}

void process_command(char* cmd) {
    cmd[strcspn(cmd, "\r\n")] = 0; // Remove newline

    if (strcmp(cmd, "id") == 0) {
        read_chip_id();
    }
    else if (strcmp(cmd, "help") == 0) {
        printf("Commands:\n");
        printf("  help           - Show this help\n");
        printf("  id             - Read chip JEDEC ID\n");
        printf("  read ADDR SIZE - Read block (hex, max 256 bytes)\n");
        printf("  dump ADDR SIZE - Dump large region\n");
        printf("  full           - Dump entire 8MB BIOS\n");
        printf("Examples:\n");
        printf("  read 0 16      - Read first 16 bytes\n");
        printf("  dump 0 100000  - Dump first 1MB\n");
    }
    else if (strncmp(cmd, "read ", 5) == 0) {
        uint32_t addr, size;
        if (sscanf(cmd + 5, "%" SCNx32 " %" SCNx32, &addr, &size) == 2) {
            read_block(addr, size);
        } else {
            printf("ERROR: Usage: read ADDR SIZE (hex)\n");
        }
    }
    else if (strncmp(cmd, "dump ", 5) == 0) {
        uint32_t addr, size;
        if (sscanf(cmd + 5, "%" SCNx32 " %" SCNx32, &addr, &size) == 2) {
            dump_flash(addr, size);
        } else {
            printf("ERROR: Usage: dump ADDR SIZE (hex)\n");
        }
    }
    else if (strcmp(cmd, "full") == 0) {
        dump_flash(0x00000000, 0x800000); // 8MB
    }
    else if (strlen(cmd) > 0) {
        printf("ERROR: Unknown command '%s'. Type 'help' for commands.\n", cmd);
    }
}

void app_main() {
    // Simple watchdog disable - just remove our task from monitoring
    esp_task_wdt_delete(xTaskGetCurrentTaskHandle());

    printf("\n=== ESP32 SPI Flash Dumper ===\n");
    printf("Watchdog disabled for long dumps\n");
    printf("Interactive mode - type 'help' for commands\n\n");

    init_spi();
    vTaskDelay(100 / portTICK_PERIOD_MS);

    char input_buffer[128];
    int pos = 0;

    printf("Ready> ");
    fflush(stdout);

    while (1) {
        int c = getchar();

        if (c == EOF) {
            // No input available, yield to other tasks
            vTaskDelay(10 / portTICK_PERIOD_MS);
            continue;
        }

        if (c == '\n' || c == '\r') {
            input_buffer[pos] = '\0';
            printf("\n");

            if (pos > 0) {
                process_command(input_buffer);
                pos = 0;
            }

            printf("Ready> ");
            fflush(stdout);
        }
        else if (c >= 32 && c <= 126 && pos < sizeof(input_buffer) - 1) {
            input_buffer[pos++] = c;
            putchar(c); // Echo character
            fflush(stdout);
        }
        else if (c == 8 || c == 127) { // Backspace
            if (pos > 0) {
                pos--;
                printf("\b \b");
                fflush(stdout);
            }
        }
    }
}
