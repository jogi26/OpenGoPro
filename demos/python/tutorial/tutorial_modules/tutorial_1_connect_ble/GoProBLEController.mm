#import <Foundation/Foundation.h>
#import <CoreBluetooth/CoreBluetooth.h>

@interface GoProBLEController : NSObject <CBCentralManagerDelegate, CBPeripheralDelegate>
@end

@implementation GoProBLEController {
    CBCentralManager *centralManager;
    CBPeripheral *goproPeripheral;
    CBCharacteristic *commandChar;
}

- (instancetype)init {
    if (self = [super init]) {
        centralManager = [[CBCentralManager alloc] initWithDelegate:self queue:nil];
    }
    return self;
}

- (void)centralManagerDidUpdateState:(CBCentralManager *)central {
    if (central.state == CBManagerStatePoweredOn) {
        NSLog(@"Scanning for GoPro BLE devices...");
        [central scanForPeripheralsWithServices:nil options:nil];
    } else {
        NSLog(@"Bluetooth not powered on or not supported.");
        exit(1);
    }
}

- (void)centralManager:(CBCentralManager *)central didDiscoverPeripheral:(CBPeripheral *)peripheral
     advertisementData:(NSDictionary<NSString *, id> *)advertisementData
                  RSSI:(NSNumber *)RSSI {
    NSString *name = peripheral.name ?: @"";
    if ([name containsString:@"GoPro"]) {
        NSLog(@"Discovered GoPro: %@", name);
        goproPeripheral = peripheral;
        goproPeripheral.delegate = self;
        [central stopScan];
        [central connectPeripheral:peripheral options:nil];
    }
}

- (void)centralManager:(CBCentralManager *)central didConnectPeripheral:(CBPeripheral *)peripheral {
    NSLog(@"Connected to %@. Discovering services...", peripheral.name);
    [peripheral discoverServices:nil];
}

- (void)peripheral:(CBPeripheral *)peripheral didDiscoverServices:(NSError *)error {
    for (CBService *service in peripheral.services) {
        [peripheral discoverCharacteristics:nil forService:service];
    }
}

- (void)peripheral:(CBPeripheral *)peripheral didDiscoverCharacteristicsForService:(CBService *)service error:(NSError *)error {
    for (CBCharacteristic *characteristic in service.characteristics) {
        // GoPro BLE command characteristic UUID (from OpenGoPro spec)
        if ([characteristic.UUID.UUIDString.lowercaseString isEqualToString:@"b5f90072-aa8d-11e3-9046-0002a5d5c51b"]) {
            commandChar = characteristic;
            NSLog(@"Command characteristic found. Sending shutter start...");

            // Start recording: 03 01 01 01
            uint8_t startCmd[] = {0x03, 0x01, 0x01, 0x01};
            NSData *data = [NSData dataWithBytes:startCmd length:sizeof(startCmd)];
            [peripheral writeValue:data forCharacteristic:commandChar type:CBCharacteristicWriteWithResponse];

            // Wait 5 seconds, then stop
            dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(5 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
                NSLog(@"Sending shutter stop...");
                uint8_t stopCmd[] = {0x03, 0x01, 0x01, 0x00};
                NSData *stopData = [NSData dataWithBytes:stopCmd length:sizeof(stopCmd)];
                [peripheral writeValue:stopData forCharacteristic:commandChar type:CBCharacteristicWriteWithResponse];
            });
        }
    }
}

@end

int main(int argc, const char * argv[]) {
    @autoreleasepool {
        GoProBLEController *controller = [[GoProBLEController alloc] init];
        [[NSRunLoop currentRunLoop] run];
    }
    return 0;
}
