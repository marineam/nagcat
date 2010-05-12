CREATE OR REPLACE PACKAGE pltest
IS
        PROCEDURE one (p_out    OUT     NUMBER);
        PROCEDURE two (p_in     IN      NUMBER,
                        p_out   OUT     NUMBER);
        PROCEDURE three (p_out  OUT     SYS_REFCURSOR);
        PROCEDURE four  (p_one  OUT     SYS_REFCURSOR,
                         p_two  OUT     SYS_REFCURSOR);
        PROCEDURE five (p_one   OUT     NUMBER,
                        p_two   OUT     NUMBER);

        PROCEDURE self_test(p_in_for_two        IN      NUMBER);
END pltest;
/

CREATE OR REPLACE PACKAGE BODY pltest
IS
        PROCEDURE one (p_out    OUT     NUMBER)
        IS
        BEGIN
                SELECT
                        TRUNC(
                                86400 * 
                                (sysdate - 
                                 TO_DATE('01-01-1970 00:00:00','MM-DD-YYYY HH24:Mi:SS')
                                )
                        )
                INTO
                        p_out
                FROM dual;
        END one;
        PROCEDURE two (p_in     IN      NUMBER,
                        p_out   OUT     NUMBER)
        IS
        BEGIN
                p_out := MOD(1234567890,p_in);
        END two;
        PROCEDURE three (p_out  OUT     SYS_REFCURSOR)
        IS
        BEGIN
                OPEN p_out FOR
                SELECT username,status,COUNT(*) AS session_ct
                FROM sys.v_$session
                WHERE type<>'BACKGROUND'
                AND username IS NOT NULL
                GROUP BY username,status;
        END three;
        PROCEDURE four  (p_one  OUT     SYS_REFCURSOR,
                         p_two  OUT     SYS_REFCURSOR)
        IS
        BEGIN
                OPEN p_one FOR
                SELECT DISTINCT machine
                FROM sys.v_$session
                WHERE type<>'BACKGROUND';

                OPEN p_two FOR
                SELECT DISTINCT machine
                FROM sys.v_$session
                WHERE type='BACKGROUND';
        END four;
        PROCEDURE five (p_one   OUT     NUMBER,
                        p_two   OUT     NUMBER)
        IS
        BEGIN
                p_one := 1;
                p_two := NULL;
        END five;

        PROCEDURE self_test(p_in_for_two        IN      NUMBER)
        IS
                v_1     NUMBER;

                v_2     NUMBER;

                v_3     sys_refcursor;
                v_3_1   VARCHAR2(30);
                v_3_2   VARCHAR2(8);
                v_3_3   NUMBER;

                v_4_1   sys_refcursor;
                v_4_1_1 VARCHAR2(64);
                v_4_2   sys_refcursor;
                v_4_2_1 VARCHAR2(64);

                v_5_1   NUMBER;
                v_5_2   NUMBER;

                ln      VARCHAR2(80) := '-------------------------------------------------';
        BEGIN
                DBMS_OUTPUT.put_line(ln);

                pltest.one(v_1);
                DBMS_OUTPUT.put_line('Test One: ');
                DBMS_OUTPUT.put_line('Current epoch seconds:  ' || v_1);
                DBMS_OUTPUT.put_line(ln);

                pltest.two(p_in_for_two,v_2);
                DBMS_OUTPUT.put_line('Test Two: ');
                DBMS_OUTPUT.put_line('1234567890 % ' || p_in_for_two || ' = ' || v_2);
                DBMS_OUTPUT.put_line(ln);

                pltest.three(v_3);
                DBMS_OUTPUT.put_line('Test Three:');
                DBMS_OUTPUT.put_line('Count of sessions by user and status:');
                LOOP
                        FETCH v_3 INTO v_3_1,v_3_2,v_3_3;
                        EXIT WHEN v_3%NOTFOUND;
                        DBMS_OUTPUT.put_line('*  ' || v_3_1 || ':  ' || v_3_3 || ' (' || v_3_2 || ')');
                END LOOP;
                DBMS_OUTPUT.put_line(ln);

                pltest.four(v_4_1,v_4_2);
                DBMS_OUTPUT.put_line('Test Four:');
                DBMS_OUTPUT.put_line('Machines with connected user processes:');
                LOOP
                        FETCH v_4_1 INTO v_4_1_1;
                        EXIT WHEN v_4_1%NOTFOUND;
                        DBMS_OUTPUT.put_line('*  ' || v_4_1_1);
                END LOOP;
                DBMS_OUTPUT.put_line('Machines with connected background processes:');
                LOOP
                        FETCH v_4_2 INTO v_4_2_1;
                        EXIT WHEN v_4_2%NOTFOUND;
                        DBMS_OUTPUT.put_line('*  ' || v_4_2_1);
                END LOOP;
                DBMS_OUTPUT.put_line(ln);

                pltest.five(v_5_1,v_5_2);
                DBMS_OUTPUT.put_line('Test Five:');
                DBMS_OUTPUT.put_line('Arbitrary number:  ' || v_5_1);
                DBMS_OUTPUT.put_line('Null Value:  ' || NVL(TO_CHAR(v_5_2),'<<NULL>>'));
                DBMS_OUTPUT.put_line(ln);
        END self_test;

END pltest;
/
