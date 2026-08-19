PRAGMA foreign_keys=ON;
UPDATE authority_state SET authority_epoch=6,authority_seq=0,mode='SERVICE_PRIMARY',scope='PRODUCTION',service_generation='session1-test-generation',updated_at='2026-08-19T06:00:00.000Z' WHERE singleton_id=1;

INSERT INTO business_dates(business_date,sequence_no,source) VALUES
('2026-08-12',93,'SESSION1_TEST'),
('2026-08-13',94,'SESSION1_TEST'),
('2026-08-14',95,'SESSION1_TEST'),
('2026-08-15',96,'SESSION1_TEST'),
('2026-08-16',97,'SESSION1_TEST'),
('2026-08-17',98,'SESSION1_TEST'),
('2026-08-18',99,'SESSION1_TEST'),
('2026-08-19',100,'SESSION1_TEST');

INSERT INTO employees(mnv,full_name,phone,main_position,supplier,department,site,warehouse,start_date,note,source_row,source_checksum) VALUES
('U001','User One','','Picker','NCC1','OPS','SITE1','KHO1','2026-01-01','',1,'seed'),
('A001','Admin One','','Picker','NCC1','OPS','SITE1','KHO1','2026-01-01','',2,'seed'),
('S001','Super One','','Picker','NCC1','OPS','SITE1','KHO1','2026-01-01','',3,'seed'),
('R001','Race One','','Picker','NCC1','OPS','SITE1','KHO1','2026-01-01','',4,'seed'),
('OLD1','Historical One','','Picker','NCC1','OPS','SITE1','KHO1','2026-01-01','',5,'seed');

INSERT INTO catalog_values(namespace,ordinal,value,source_checksum) VALUES
('DANH SÁCH NHÂN SỰ_Vị trí chính',1,'Picker','seed'),
('DANH SÁCH NHÂN SỰ_Nhà cung cấp',1,'NCC1','seed'),
('DANH SÁCH NHÂN SỰ_Bộ phận',1,'OPS','seed'),
('DANH SÁCH NHÂN SỰ_Site',1,'SITE1','seed'),
('DANH SÁCH NHÂN SỰ_Kho',1,'KHO1','seed'),
('DANH SÁCH PDA_Tình trạng',1,'Hoạt động','seed'),
('DANH SÁCH PDA_Tình trạng',2,'Tạm ngưng','seed'),
('DANH SÁCH USER PICK_Tình trạng',1,'Hoạt động','seed'),
('DANH SÁCH BÀN PACK_Tình trạng',1,'Hoạt động','seed'),
('DANH SÁCH BÀN PACK_Tình trạng',2,'Tạm ngưng','seed'),
('DANH SÁCH USER PACK_Tình trạng',1,'Hoạt động','seed'),
('RA - VÀO TRONG CA_Loại thao tác',1,'Vào ca','seed'),
('RA - VÀO TRONG CA_Loại thao tác',2,'Ra ca','seed'),
('VÀO - RA TRONG CA_Ca',1,'CA1','seed'),
('CÔNG NHẬT_Thông tin công nhật',1,'Tăng cường','seed'),
('CÔNG NHẬT_Mốc thời gian',1,'Bắt đầu','seed'),
('CÔNG NHẬT_Mốc thời gian',2,'Kết thúc','seed'),
('CÔNG NHẬT_Trạng thái',1,'Hoàn thành','seed');

INSERT INTO resources(resource_type,resource_id,status_label,available,metadata_json,source_row,source_checksum) VALUES
('PDA','PDA001','Hoạt động',1,'{}',1,'seed'),
('PDA','PDA002','Hoạt động',1,'{}',2,'seed'),
('USER_PICK','PICK001','Hoạt động',1,'{}',3,'seed'),
('USER_PACK','PACK001','Hoạt động',1,'{}',4,'seed'),
('PACK_TABLE','TABLE001','Hoạt động',1,'{}',5,'seed');

INSERT INTO attendance_sessions(session_id,mnv,business_date,shift,work_choice,state,pda_serial,user_pick,pack_table,user_pack,enter_at,exit_at,entered_by,exited_by,version,source_last_row,updated_at)
VALUES('hist-old-1','OLD1','2026-08-12','CA1','KHONG','ENDED',NULL,NULL,NULL,NULL,'2026-08-12T01:00:00Z','2026-08-12T09:00:00Z','seed','seed',1,0,'2026-08-12T09:00:00Z');
